"""Huey queue definitions and enqueue helpers."""

from __future__ import annotations

from huey import SqliteHuey

from app.core.settings import PATHS
from app.services.pipeline import execute_job

huey = SqliteHuey("videobling", filename=str(PATHS.queue_path))


@huey.task(retries=0)
def run_job_task(job_id: str) -> None:
    execute_job(job_id)


def enqueue_job(job_id: str) -> None:
    run_job_task(job_id)
