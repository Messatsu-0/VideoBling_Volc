"""Persistence helpers for jobs and events."""

from __future__ import annotations

import json
from typing import Iterable, Optional, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import JobStatus, RUNNING_STATES, TERMINAL_STATES
from app.models.job import Job, JobEvent
from app.schemas.job import JobOut


def _json_load(value: str) -> dict[str, object]:
    try:
        return json.loads(value)
    except Exception:
        return {}


def to_job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        project_name=job.project_name,
        input_filename=job.input_filename,
        source_path=job.source_path,
        asr_clip_seconds=job.asr_clip_seconds,
        hook_clip_seconds=job.hook_clip_seconds,
        status=job.status,
        error_message=job.error_message,
        artifacts={k: str(v) for k, v in _json_load(job.artifacts_json).items()},
        meta=_json_load(job.meta_json),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def create_job(
    db: Session,
    *,
    job_id: str,
    project_name: str,
    input_filename: str,
    source_path: str,
    asr_clip_seconds: int,
    hook_clip_seconds: int,
) -> Job:
    job = Job(
        id=job_id,
        project_name=project_name,
        input_filename=input_filename,
        source_path=source_path,
        asr_clip_seconds=asr_clip_seconds,
        hook_clip_seconds=hook_clip_seconds,
        status=JobStatus.QUEUED.value,
        meta_json="{}",
        artifacts_json="{}",
    )
    db.add(job)
    db.flush()
    append_event(db, job_id, JobStatus.QUEUED.value, "任务已进入队列")
    return job


def list_jobs(db: Session) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc())
    return list(db.scalars(stmt))


def get_job(db: Session, job_id: str) -> Optional[Job]:
    return db.get(Job, job_id)


def delete_job(db: Session, job_id: str) -> bool:
    job = get_job(db, job_id)
    if not job:
        return False
    db.delete(job)
    db.flush()
    return True


def set_job_status(
    db: Session,
    job_id: str,
    status: Union[JobStatus, str],
    message: Optional[str] = None,
) -> Job:
    job = get_job(db, job_id)
    if not job:
        raise ValueError(f"job not found: {job_id}")

    job.status = status.value if isinstance(status, JobStatus) else status
    if message:
        append_event(db, job_id, job.status, message)
    db.flush()
    return job


def set_job_error(db: Session, job_id: str, error_message: str) -> Job:
    job = get_job(db, job_id)
    if not job:
        raise ValueError(f"job not found: {job_id}")
    job.status = JobStatus.FAILED.value
    job.error_message = error_message
    append_event(db, job_id, JobStatus.FAILED.value, error_message)
    db.flush()
    return job


def patch_meta(db: Session, job_id: str, **kwargs: object) -> Job:
    job = get_job(db, job_id)
    if not job:
        raise ValueError(f"job not found: {job_id}")
    meta = _json_load(job.meta_json)
    meta.update(kwargs)
    job.meta_json = json.dumps(meta, ensure_ascii=False)
    db.flush()
    return job


def put_artifact(db: Session, job_id: str, kind: str, path: str) -> Job:
    job = get_job(db, job_id)
    if not job:
        raise ValueError(f"job not found: {job_id}")
    artifacts = _json_load(job.artifacts_json)
    artifacts[kind] = path
    job.artifacts_json = json.dumps(artifacts, ensure_ascii=False)
    db.flush()
    return job


def append_event(db: Session, job_id: str, status: str, message: str) -> JobEvent:
    event = JobEvent(job_id=job_id, status=status, message=message)
    db.add(event)
    db.flush()
    return event


def list_events(db: Session, job_id: str, after_id: int = 0) -> list[JobEvent]:
    stmt = (
        select(JobEvent)
        .where(JobEvent.job_id == job_id, JobEvent.id > after_id)
        .order_by(JobEvent.id.asc())
    )
    return list(db.scalars(stmt))


def reset_running_jobs_to_queued(db: Session) -> Iterable[str]:
    stmt = select(Job).where(Job.status.in_([s.value for s in RUNNING_STATES]))
    jobs = list(db.scalars(stmt))
    reset_ids: list[str] = []
    for job in jobs:
        job.status = JobStatus.QUEUED.value
        append_event(db, job.id, JobStatus.QUEUED.value, "检测到重启，任务重新入队")
        reset_ids.append(job.id)
    db.flush()
    return reset_ids


def list_queued_jobs(db: Session) -> list[str]:
    stmt = select(Job.id).where(Job.status == JobStatus.QUEUED.value).order_by(Job.created_at.asc())
    return list(db.scalars(stmt))


def trim_jobs(db: Session, keep_latest: int = 20) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc())
    jobs = list(db.scalars(stmt))
    terminal_jobs = [job for job in jobs if job.status in {state.value for state in TERMINAL_STATES}]
    removable = terminal_jobs[keep_latest:]
    for job in removable:
        db.delete(job)
    db.flush()
    return removable
