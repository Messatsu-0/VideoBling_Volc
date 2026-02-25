"""Pydantic schemas for job API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobRerunRequest(BaseModel):
    start_stage: str = "preprocessing"
    project_name: Optional[str] = None


class JobEventOut(BaseModel):
    id: int
    job_id: str
    status: str
    message: str
    created_at: datetime


class JobOut(BaseModel):
    id: str
    project_name: str
    input_filename: str
    source_path: str
    asr_clip_seconds: int
    hook_clip_seconds: int
    status: str
    error_message: Optional[str]
    artifacts: dict[str, str]
    meta: dict[str, object]
    created_at: datetime
    updated_at: datetime
