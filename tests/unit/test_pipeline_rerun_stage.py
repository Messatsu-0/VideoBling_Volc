from __future__ import annotations

from app.core.constants import JobStatus
from app.services.pipeline import _normalize_start_stage, _should_run_stage


def test_normalize_start_stage() -> None:
    assert _normalize_start_stage("script_gen") == JobStatus.SCRIPT_GEN
    assert _normalize_start_stage("VIDEO_SUBMIT") == JobStatus.VIDEO_SUBMIT
    assert _normalize_start_stage("unknown") == JobStatus.PREPROCESSING


def test_should_run_stage_order() -> None:
    start = JobStatus.SCRIPT_GEN
    assert _should_run_stage(start, JobStatus.SCRIPT_GEN) is True
    assert _should_run_stage(start, JobStatus.VIDEO_SUBMIT) is True
    assert _should_run_stage(start, JobStatus.ASR) is False
