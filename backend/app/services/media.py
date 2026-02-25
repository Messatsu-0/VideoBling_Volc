"""Media processing helpers powered by ffmpeg/ffprobe."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class MediaError(RuntimeError):
    pass


@dataclass
class VideoMeta:
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise MediaError(f"Command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc


def ffmpeg_available() -> bool:
    try:
        _run(["ffmpeg", "-version"])
        return True
    except Exception:
        return False


def ffprobe_available() -> bool:
    try:
        _run(["ffprobe", "-version"])
        return True
    except Exception:
        return False


def _fps_value(rate: Optional[str]) -> float:
    if not rate:
        return 30.0
    if "/" in rate:
        n, d = rate.split("/", maxsplit=1)
        try:
            denom = float(d)
            if denom == 0:
                return 30.0
            return float(n) / denom
        except Exception:
            return 30.0
    try:
        return float(rate)
    except Exception:
        return 30.0


def probe_video(path: Path) -> VideoMeta:
    proc = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(proc.stdout)
    streams = payload.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video_stream:
        raise MediaError("No video stream found")

    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = video_stream.get("duration") or payload.get("format", {}).get("duration") or 0
    return VideoMeta(
        width=int(video_stream.get("width") or 1080),
        height=int(video_stream.get("height") or 1920),
        fps=max(_fps_value(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")), 1.0),
        duration=float(duration),
        has_audio=audio_stream is not None,
    )


def extract_asr_clip_to_wav(source_video: Path, clip_seconds: int, wav_output: Path) -> None:
    wav_output.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source_video),
            "-t",
            str(max(1, int(clip_seconds))),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-vn",
            "-c:a",
            "pcm_s16le",
            str(wav_output),
        ]
    )


def _scale_pad_filter(width: int, height: int, fps: float) -> str:
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps:.3f}"
    )


def normalize_source_video(source_video: Path, target: VideoMeta, output_video: Path) -> None:
    output_video.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source_video),
            "-vf",
            _scale_pad_filter(target.width, target.height, target.fps),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ac",
            "2",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(output_video),
        ]
    )


def normalize_hook_video(
    hook_video_raw: Path,
    target: VideoMeta,
    hook_seconds: int,
    output_video: Path,
) -> None:
    output_video.parent.mkdir(parents=True, exist_ok=True)
    normalized = output_video.parent / "hook_video_aligned.mp4"
    raw_meta = probe_video(hook_video_raw)
    filter_expr = _scale_pad_filter(target.width, target.height, target.fps)

    if raw_meta.has_audio:
        _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(hook_video_raw),
                "-vf",
                filter_expr,
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ac",
                "2",
                "-ar",
                "48000",
                str(normalized),
            ]
        )
    else:
        _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(hook_video_raw),
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-vf",
                filter_expr,
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(normalized),
            ]
        )

    aligned_meta = probe_video(normalized)
    target_seconds = max(1, int(hook_seconds))

    if aligned_meta.duration >= target_seconds:
        _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(normalized),
                "-t",
                str(target_seconds),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ac",
                "2",
                "-ar",
                "48000",
                str(output_video),
            ]
        )
        return

    pad_seconds = max(0.0, target_seconds - aligned_meta.duration)
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(normalized),
            "-vf",
            f"tpad=stop_mode=clone:stop_duration={pad_seconds:.3f}",
            "-af",
            f"apad=pad_dur={pad_seconds:.3f}",
            "-t",
            str(target_seconds),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ac",
            "2",
            "-ar",
            "48000",
            str(output_video),
        ]
    )


def concat_with_source(hook_video: Path, source_video: Path, output_video: Path) -> None:
    output_video.parent.mkdir(parents=True, exist_ok=True)
    concat_txt = output_video.parent / "concat_list.txt"
    concat_txt.write_text(
        f"file '{hook_video.as_posix()}'\nfile '{source_video.as_posix()}'\n",
        encoding="utf-8",
    )

    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ac",
            "2",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(output_video),
        ]
    )


def dump_meta(meta: VideoMeta, path: Path) -> None:
    path.write_text(json.dumps(meta.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
