"""Project-wide constants and state definitions."""

from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "queued"
    PREPROCESSING = "preprocessing"
    ASR = "asr"
    TRANSCRIPT_POLISH = "transcript_polish"
    SCRIPT_GEN = "script_gen"
    VIDEO_SUBMIT = "video_submit"
    VIDEO_POLLING = "video_polling"
    POSTPROCESS = "postprocess"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


RUNNING_STATES = {
    JobStatus.PREPROCESSING,
    JobStatus.ASR,
    JobStatus.TRANSCRIPT_POLISH,
    JobStatus.SCRIPT_GEN,
    JobStatus.VIDEO_SUBMIT,
    JobStatus.VIDEO_POLLING,
    JobStatus.POSTPROCESS,
}

TERMINAL_STATES = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELED}

ARTIFACT_KINDS = {
    "source_video",
    "asr_clip_audio",
    "transcript_raw",
    "transcript_polished",
    "hook_script_json",
    "hook_video_raw",
    "hook_video_norm",
    "final_video",
}
