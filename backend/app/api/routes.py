"""FastAPI route definitions."""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.core.constants import ARTIFACT_KINDS, TERMINAL_STATES
from app.core.constants import JobStatus
from app.core.settings import APP_VERSION, PATHS
from app.db.session import SessionLocal, get_db_session
from app.schemas.config import AppConfig, ConfigPresetOut, ConfigPresetSummary
from app.schemas.job import JobCreateResponse, JobEventOut, JobOut, JobRerunRequest
from app.services import repository
from app.services.config_store import (
    delete_config_preset,
    get_config_preset,
    list_config_presets,
    load_config,
    save_config,
    save_config_preset,
)
from app.services.media import ffmpeg_available, ffprobe_available
from app.workers.queue import enqueue_job

router = APIRouter(prefix="/api", tags=["api"])
RERUN_START_STAGES = {
    JobStatus.PREPROCESSING.value,
    JobStatus.ASR.value,
    JobStatus.TRANSCRIPT_POLISH.value,
    JobStatus.SCRIPT_GEN.value,
    JobStatus.VIDEO_SUBMIT.value,
    JobStatus.VIDEO_POLLING.value,
    JobStatus.POSTPROCESS.value,
}


def _job_dir(job_id: str) -> Path:
    return PATHS.jobs_root / job_id


async def _save_upload(upload: UploadFile, target: Path, max_bytes: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target.open("wb") as f:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                raise HTTPException(status_code=413, detail="Uploaded file exceeds max size")
            f.write(chunk)


@router.get("/health")
def health(db: Session = Depends(get_db_session)) -> dict[str, object]:
    queued = len(repository.list_queued_jobs(db))
    return {
        "version": APP_VERSION,
        "ffmpeg_available": ffmpeg_available(),
        "ffprobe_available": ffprobe_available(),
        "queue_db": str(PATHS.queue_path),
        "queued_jobs": queued,
    }


@router.get("/config", response_model=AppConfig)
def get_config() -> AppConfig:
    return load_config()


@router.put("/config", response_model=AppConfig)
def put_config(config: AppConfig) -> AppConfig:
    return save_config(config)


@router.get("/config/presets", response_model=list[ConfigPresetSummary])
def get_config_presets() -> list[ConfigPresetSummary]:
    return list_config_presets()


@router.get("/config/presets/{preset_name}", response_model=ConfigPresetOut)
def get_config_preset_detail(preset_name: str) -> ConfigPresetOut:
    try:
        preset = get_config_preset(preset_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    return preset


@router.put("/config/presets/{preset_name}", response_model=ConfigPresetOut)
def put_config_preset(preset_name: str, config: AppConfig) -> ConfigPresetOut:
    try:
        return save_config_preset(preset_name, config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/config/presets/{preset_name}")
def remove_config_preset(preset_name: str) -> dict[str, object]:
    try:
        deleted = delete_config_preset(preset_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"deleted": True, "name": preset_name}


@router.post("/jobs", response_model=JobCreateResponse)
async def create_job(
    project_name: str = Form(""),
    asr_clip_seconds: int = Form(15, ge=1, le=120),
    hook_clip_seconds: int = Form(5, ge=1, le=20),
    video_file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
) -> JobCreateResponse:
    config = load_config()
    max_bytes = int(config.pipeline.max_upload_mb) * 1024 * 1024

    if not video_file.filename:
        raise HTTPException(status_code=400, detail="video_file filename is required")

    job_id = uuid.uuid4().hex
    raw_name = Path(video_file.filename).name
    job_dir = _job_dir(job_id)
    source_path = job_dir / f"source_{raw_name}"

    await _save_upload(video_file, source_path, max_bytes)

    project = project_name.strip() or Path(raw_name).stem or "Untitled"
    repository.create_job(
        db,
        job_id=job_id,
        project_name=project,
        input_filename=raw_name,
        source_path=str(source_path),
        asr_clip_seconds=asr_clip_seconds,
        hook_clip_seconds=hook_clip_seconds,
    )
    db.commit()

    enqueue_job(job_id)
    return JobCreateResponse(job_id=job_id, status="queued")


@router.post("/jobs/{job_id}/rerun", response_model=JobCreateResponse)
def rerun_job(job_id: str, payload: JobRerunRequest, db: Session = Depends(get_db_session)) -> JobCreateResponse:
    parent = repository.get_job(db, job_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Job not found")

    start_stage = payload.start_stage.strip().lower()
    if start_stage not in RERUN_START_STAGES:
        allowed = ", ".join(sorted(RERUN_START_STAGES))
        raise HTTPException(status_code=400, detail=f"Invalid start_stage: {start_stage}. Allowed: {allowed}")

    source_path = Path(parent.source_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Source video not found: {source_path}")

    rerun_job_id = uuid.uuid4().hex
    rerun_dir = _job_dir(rerun_job_id)
    rerun_dir.mkdir(parents=True, exist_ok=True)
    rerun_source_path = rerun_dir / source_path.name
    shutil.copy2(source_path, rerun_source_path)

    project_name = (payload.project_name or "").strip() or f"{parent.project_name} · rerun"
    repository.create_job(
        db,
        job_id=rerun_job_id,
        project_name=project_name,
        input_filename=parent.input_filename,
        source_path=str(rerun_source_path),
        asr_clip_seconds=parent.asr_clip_seconds,
        hook_clip_seconds=parent.hook_clip_seconds,
    )
    repository.patch_meta(
        db,
        rerun_job_id,
        rerun_of_job_id=parent.id,
        rerun_start_stage=start_stage,
    )
    db.commit()

    enqueue_job(rerun_job_id)
    return JobCreateResponse(job_id=rerun_job_id, status="queued")


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db_session)) -> list[JobOut]:
    return [repository.to_job_out(job) for job in repository.list_jobs(db)]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db_session)) -> JobOut:
    job = repository.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return repository.to_job_out(job)


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, force: bool = Query(True), db: Session = Depends(get_db_session)) -> dict[str, object]:
    job = repository.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not force and all(job.status != state.value for state in TERMINAL_STATES):
        raise HTTPException(
            status_code=409,
            detail="Job is not terminal. Set force=true to delete queued/running jobs.",
        )

    deleted = repository.delete_job(db, job_id)
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")

    target = _job_dir(job_id)
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)

    return {"deleted": True, "job_id": job_id, "force": force}


@router.get("/jobs/{job_id}/events")
async def stream_job_events(job_id: str, db: Session = Depends(get_db_session)) -> EventSourceResponse:
    exists = repository.get_job(db, job_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_id = 0
        while True:
            with SessionLocal() as session:
                events = repository.list_events(session, job_id, after_id=last_id)
                job = repository.get_job(session, job_id)

            for event in events:
                last_id = event.id
                payload = JobEventOut.model_validate(event, from_attributes=True).model_dump(mode="json")
                yield {
                    "event": "job_event",
                    "id": str(event.id),
                    "data": json.dumps(payload, ensure_ascii=False),
                }

            if job and any(job.status == state.value for state in TERMINAL_STATES) and not events:
                yield {"event": "end", "data": json.dumps({"job_id": job_id})}
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@router.get("/jobs/{job_id}/artifacts/{kind}")
def get_artifact(kind: str, job_id: str, db: Session = Depends(get_db_session)) -> FileResponse:
    if kind not in ARTIFACT_KINDS:
        raise HTTPException(status_code=400, detail="Unsupported artifact kind")

    job = repository.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    artifacts = repository.to_job_out(job).artifacts
    path = artifacts.get(kind)
    if not path:
        raise HTTPException(status_code=404, detail="Artifact not found")

    artifact_path = Path(path)
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file does not exist")

    media_type = "application/octet-stream"
    if artifact_path.suffix == ".mp4":
        media_type = "video/mp4"
    elif artifact_path.suffix == ".json":
        media_type = "application/json"
    elif artifact_path.suffix in {".txt", ".log"}:
        media_type = "text/plain"

    return FileResponse(path=str(artifact_path), media_type=media_type, filename=artifact_path.name)


@router.post("/jobs/cleanup")
def cleanup_jobs(keep_latest: int = Query(20, ge=1, le=200), db: Session = Depends(get_db_session)) -> dict[str, object]:
    removed_jobs = repository.trim_jobs(db, keep_latest=keep_latest)
    db.commit()

    removed_ids = [job.id for job in removed_jobs]
    for job_id in removed_ids:
        target = _job_dir(job_id)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)

    return {"removed": removed_ids, "keep_latest": keep_latest}
