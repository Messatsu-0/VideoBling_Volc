"""End-to-end job execution pipeline."""

from __future__ import annotations

import json
import shutil
import textwrap
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.constants import JobStatus
from app.core.settings import PATHS
from app.db.session import SessionLocal
from app.services import repository
from app.services.config_store import load_config
from app.services.media import (
    VideoMeta,
    concat_with_source,
    dump_meta,
    extract_asr_clip_to_wav,
    ffmpeg_available,
    ffprobe_available,
    normalize_hook_video,
    normalize_source_video,
    probe_video,
)
from app.services.script_schema import validate_script_payload
from app.services.volc_clients import ASRClient, LLMClient, VideoClient, extract_first_json_object, parse_asr_text


class PipelineError(RuntimeError):
    pass


STAGE_SEQUENCE = [
    JobStatus.PREPROCESSING,
    JobStatus.ASR,
    JobStatus.TRANSCRIPT_POLISH,
    JobStatus.SCRIPT_GEN,
    JobStatus.VIDEO_SUBMIT,
    JobStatus.VIDEO_POLLING,
    JobStatus.POSTPROCESS,
]


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _set_stage(db: Session, job_id: str, status: JobStatus, message: str) -> None:
    repository.set_job_status(db, job_id, status, message)
    db.commit()


def _save_artifact(db: Session, job_id: str, kind: str, path: Path) -> None:
    repository.put_artifact(db, job_id, kind, str(path))
    db.commit()


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _normalize_start_stage(value: object) -> JobStatus:
    raw = str(value or JobStatus.PREPROCESSING.value).strip().lower()
    for status in STAGE_SEQUENCE:
        if status.value == raw:
            return status
    return JobStatus.PREPROCESSING


def _should_run_stage(start_stage: JobStatus, stage: JobStatus) -> bool:
    return STAGE_SEQUENCE.index(stage) >= STAGE_SEQUENCE.index(start_stage)


def _safe_float(value: object, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _video_meta_from_dict(payload: dict[str, object]) -> Optional[VideoMeta]:
    if not payload:
        return None
    if not {"width", "height", "fps", "duration", "has_audio"}.issubset(payload.keys()):
        return None
    return VideoMeta(
        width=max(1, _safe_int(payload.get("width"), 1080)),
        height=max(1, _safe_int(payload.get("height"), 1920)),
        fps=max(1.0, _safe_float(payload.get("fps"), 30.0)),
        duration=max(0.0, _safe_float(payload.get("duration"), 0.0)),
        has_audio=bool(payload.get("has_audio")),
    )


def _reuse_parent_artifact(
    db: Session,
    *,
    job_id: str,
    parent_job_id: str,
    parent_artifacts: dict[str, str],
    kind: str,
    target_path: Path,
    required: bool,
) -> Optional[Path]:
    parent_path_text = parent_artifacts.get(kind)
    if not parent_path_text:
        if required:
            raise PipelineError(f"重跑需复用产物 `{kind}`，但父任务 {parent_job_id} 缺少该产物")
        return None

    parent_path = Path(parent_path_text)
    if not parent_path.exists():
        if required:
            raise PipelineError(f"重跑需复用产物 `{kind}`，但文件不存在: {parent_path}")
        return None

    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(parent_path, target_path)
    _save_artifact(db, job_id, kind, target_path)
    return target_path


def _read_text_or_fail(path: Path, error_message: str) -> str:
    try:
        content = path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        raise PipelineError(error_message) from exc
    if not content:
        raise PipelineError(error_message)
    return content


def _build_polish_prompt(raw_transcript: str) -> str:
    return textwrap.dedent(
        f"""
        以下是ASR转写文本，请只做纠错、断句和轻微可读性优化。
        不要扩写内容，不要改变事实，不要新增剧情。

        原始文本：
        {raw_transcript}
        """
    ).strip()


def _build_script_prompt(polished_transcript: str, hook_seconds: int) -> str:
    return textwrap.dedent(
        f"""
        基于以下文本，生成一个用于短视频导流的前贴脚本，时长目标 {hook_seconds} 秒。
        风格要求：荒诞、有趣、吸睛、节奏快、画面冲击强。

        输出必须是严格JSON对象，字段如下：
        hook_title: string
        visual_prompt: string
        shot_list: string[]
        narration: string
        style_tags: string[]
        safety_notes: string

        输入文本：
        {polished_transcript}
        """
    ).strip()


def _build_video_prompt(video_system_prompt: str, script_payload: dict) -> str:
    shot_lines = "\n".join(f"- {item}" for item in script_payload.get("shot_list", []))
    style_tags = ", ".join(script_payload.get("style_tags", []))
    return textwrap.dedent(
        f"""
        {video_system_prompt}

        标题：{script_payload.get("hook_title", "")}
        视觉描述：{script_payload.get("visual_prompt", "")}
        分镜：
        {shot_lines}

        旁白：{script_payload.get("narration", "")}
        风格标签：{style_tags}
        安全约束：{script_payload.get("safety_notes", "")}
        """
    ).strip()


def execute_job(job_id: str) -> None:
    db = SessionLocal()
    asr_client = ASRClient()
    llm_client = LLMClient()
    video_client = VideoClient()

    try:
        job = repository.get_job(db, job_id)
        if not job:
            return

        config = load_config()
        job_dir = PATHS.jobs_root / job.id
        job_dir.mkdir(parents=True, exist_ok=True)

        job.error_message = None
        db.commit()

        job_out = repository.to_job_out(job)
        job_meta = job_out.meta
        start_stage = _normalize_start_stage(job_meta.get("rerun_start_stage"))
        parent_job_id = str(job_meta.get("rerun_of_job_id") or "").strip()
        parent_meta: dict[str, object] = {}
        parent_artifacts: dict[str, str] = {}
        if parent_job_id:
            parent_job = repository.get_job(db, parent_job_id)
            if not parent_job:
                raise PipelineError(f"重跑父任务不存在: {parent_job_id}")
            parent_out = repository.to_job_out(parent_job)
            parent_meta = parent_out.meta
            parent_artifacts = parent_out.artifacts
            repository.append_event(
                db,
                job.id,
                JobStatus.QUEUED.value,
                f"重跑任务：从 `{start_stage.value}` 开始，复用父任务 `{parent_job_id}` 产物",
            )
            db.commit()

        source_video_path = Path(job.source_path)
        if not source_video_path.exists():
            raise PipelineError(f"源视频不存在: {source_video_path}")

        if not ffmpeg_available() or not ffprobe_available():
            raise PipelineError("ffmpeg 或 ffprobe 不可用，请先安装")

        _save_artifact(db, job.id, "source_video", source_video_path)

        if _should_run_stage(start_stage, JobStatus.PREPROCESSING):
            _set_stage(db, job.id, JobStatus.PREPROCESSING, "开始预处理视频")
            source_meta = probe_video(source_video_path)
        else:
            _set_stage(db, job.id, JobStatus.PREPROCESSING, "跳过预处理，复用父任务元数据")
            source_meta = _video_meta_from_dict(_as_dict(parent_meta.get("source_meta")))
            if not source_meta:
                source_meta = probe_video(source_video_path)

        source_meta_path = job_dir / "source_meta.json"
        dump_meta(source_meta, source_meta_path)
        repository.patch_meta(db, job.id, source_meta=source_meta.__dict__)
        db.commit()

        if _should_run_stage(start_stage, JobStatus.ASR):
            _set_stage(db, job.id, JobStatus.ASR, "正在截取音频并调用ASR")
            asr_audio_path = job_dir / "asr_clip.wav"
            extract_asr_clip_to_wav(source_video_path, job.asr_clip_seconds, asr_audio_path)
            _save_artifact(db, job.id, "asr_clip_audio", asr_audio_path)

            asr_raw_payload = asr_client.recognize(config.asr, asr_audio_path)
            _write_json(job_dir / "asr_response.json", asr_raw_payload)

            transcript_raw = parse_asr_text(asr_raw_payload).strip()
            if not transcript_raw:
                raise PipelineError("ASR识别结果为空")

            transcript_raw_path = job_dir / "transcript_raw.txt"
            _write_text(transcript_raw_path, transcript_raw)
            _save_artifact(db, job.id, "transcript_raw", transcript_raw_path)
        else:
            _set_stage(db, job.id, JobStatus.ASR, "跳过ASR，复用父任务转写产物")
            _reuse_parent_artifact(
                db,
                job_id=job.id,
                parent_job_id=parent_job_id,
                parent_artifacts=parent_artifacts,
                kind="asr_clip_audio",
                target_path=job_dir / "asr_clip.wav",
                required=False,
            )
            reused_transcript_raw_path = _reuse_parent_artifact(
                db,
                job_id=job.id,
                parent_job_id=parent_job_id,
                parent_artifacts=parent_artifacts,
                kind="transcript_raw",
                target_path=job_dir / "transcript_raw.txt",
                required=True,
            )
            if reused_transcript_raw_path is None:
                raise PipelineError("复用 transcript_raw 失败")
            transcript_raw = _read_text_or_fail(reused_transcript_raw_path, "复用转写文本为空")

        if _should_run_stage(start_stage, JobStatus.TRANSCRIPT_POLISH):
            if config.pipeline.enable_asr_polish:
                _set_stage(db, job.id, JobStatus.TRANSCRIPT_POLISH, "ASR文本纠错中")
                polish_system_prompt = config.asr.system_prompt or config.llm.asr_polish_system_prompt
                polish_user_prompt = _build_polish_prompt(transcript_raw)
                polished_text, polish_raw_payload = llm_client.generate_text(
                    config.llm,
                    system_prompt=polish_system_prompt,
                    user_prompt=polish_user_prompt,
                    temperature=0.2,
                )
                _write_json(job_dir / "transcript_polish_response.json", polish_raw_payload)
                polished_text = polished_text.strip() or transcript_raw
            else:
                _set_stage(db, job.id, JobStatus.TRANSCRIPT_POLISH, "ASR文本纠错已关闭，直接使用原始转写")
                polished_text = transcript_raw

            transcript_polished_path = job_dir / "transcript_polished.txt"
            _write_text(transcript_polished_path, polished_text)
            _save_artifact(db, job.id, "transcript_polished", transcript_polished_path)
        else:
            _set_stage(db, job.id, JobStatus.TRANSCRIPT_POLISH, "跳过纠错，复用父任务文本")
            reused_polished_path = _reuse_parent_artifact(
                db,
                job_id=job.id,
                parent_job_id=parent_job_id,
                parent_artifacts=parent_artifacts,
                kind="transcript_polished",
                target_path=job_dir / "transcript_polished.txt",
                required=True,
            )
            if reused_polished_path is None:
                raise PipelineError("复用 transcript_polished 失败")
            polished_text = _read_text_or_fail(reused_polished_path, "复用纠错文本为空")

        if _should_run_stage(start_stage, JobStatus.SCRIPT_GEN):
            _set_stage(db, job.id, JobStatus.SCRIPT_GEN, "生成前贴脚本中")
            script_user_prompt = _build_script_prompt(polished_text, job.hook_clip_seconds)
            script_text, script_raw_payload = llm_client.generate_text(
                config.llm,
                system_prompt=config.llm.script_system_prompt,
                user_prompt=script_user_prompt,
                temperature=config.llm.temperature,
            )
            _write_json(job_dir / "script_gen_response.json", script_raw_payload)

            script_payload = extract_first_json_object(script_text)
            script_payload = validate_script_payload(script_payload)
            hook_script_path = job_dir / "hook_script.json"
            _write_json(hook_script_path, script_payload)
            _save_artifact(db, job.id, "hook_script_json", hook_script_path)
        else:
            _set_stage(db, job.id, JobStatus.SCRIPT_GEN, "跳过脚本生成，复用父任务脚本")
            reused_script_path = _reuse_parent_artifact(
                db,
                job_id=job.id,
                parent_job_id=parent_job_id,
                parent_artifacts=parent_artifacts,
                kind="hook_script_json",
                target_path=job_dir / "hook_script.json",
                required=True,
            )
            if reused_script_path is None:
                raise PipelineError("复用 hook_script_json 失败")
            try:
                script_payload = json.loads(reused_script_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise PipelineError("复用脚本JSON解析失败") from exc
            script_payload = validate_script_payload(script_payload)

        if _should_run_stage(start_stage, JobStatus.VIDEO_SUBMIT):
            _set_stage(db, job.id, JobStatus.VIDEO_SUBMIT, "提交视频生成任务")
            video_prompt = _build_video_prompt(config.video.system_prompt, script_payload)
            task_id, submit_raw_payload = video_client.submit_generation(
                config.video,
                prompt=video_prompt,
                duration_s=job.hook_clip_seconds,
                width=source_meta.width,
                height=source_meta.height,
            )
            _write_json(job_dir / "video_submit_response.json", submit_raw_payload)
            repository.patch_meta(db, job.id, video_task_id=task_id)
            db.commit()
        else:
            _set_stage(db, job.id, JobStatus.VIDEO_SUBMIT, "跳过视频提交，复用父任务 task_id")
            task_id = str(parent_meta.get("video_task_id") or "").strip()
            if not task_id:
                raise PipelineError(
                    f"重跑从 `{start_stage.value}` 开始需要复用 video_task_id，但父任务 `{parent_job_id}` 未记录"
                )
            repository.patch_meta(db, job.id, video_task_id=task_id)
            db.commit()

        if _should_run_stage(start_stage, JobStatus.VIDEO_POLLING):
            _set_stage(db, job.id, JobStatus.VIDEO_POLLING, f"轮询视频任务中: {task_id}")
            video_result = video_client.poll_until_done(config.video, task_id)
            _write_json(job_dir / "video_poll_response.json", video_result)
            video_url = video_client.extract_video_url(video_result)

            hook_video_raw_path = job_dir / "hook_video_raw.mp4"
            video_client.download_video(video_url, hook_video_raw_path)
            _save_artifact(db, job.id, "hook_video_raw", hook_video_raw_path)
        else:
            _set_stage(db, job.id, JobStatus.VIDEO_POLLING, "跳过视频轮询，复用父任务前贴视频")
            reused_hook_raw = _reuse_parent_artifact(
                db,
                job_id=job.id,
                parent_job_id=parent_job_id,
                parent_artifacts=parent_artifacts,
                kind="hook_video_raw",
                target_path=job_dir / "hook_video_raw.mp4",
                required=True,
            )
            if reused_hook_raw is None:
                raise PipelineError("复用 hook_video_raw 失败")
            hook_video_raw_path = reused_hook_raw

        _set_stage(db, job.id, JobStatus.POSTPROCESS, "标准化前贴并拼接成片")

        source_norm_path = job_dir / "source_video_norm.mp4"
        normalize_source_video(source_video_path, source_meta, source_norm_path)

        hook_video_norm_path = job_dir / "hook_video_norm.mp4"
        normalize_hook_video(
            hook_video_raw_path,
            source_meta,
            job.hook_clip_seconds,
            hook_video_norm_path,
        )
        _save_artifact(db, job.id, "hook_video_norm", hook_video_norm_path)

        final_video_path = job_dir / "final_video.mp4"
        concat_with_source(hook_video_norm_path, source_norm_path, final_video_path)
        _save_artifact(db, job.id, "final_video", final_video_path)

        repository.set_job_status(db, job.id, JobStatus.COMPLETED, "任务完成，成片已输出")
        db.commit()

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        try:
            repository.set_job_error(db, job_id, str(exc))
            db.commit()
        except Exception:
            db.rollback()
        raise
    finally:
        db.close()
