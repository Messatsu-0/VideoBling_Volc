"""Pydantic schemas for persisted app configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ASRConfig(BaseModel):
    base_url: str = "https://openspeech.bytedance.com"
    appid: str = ""
    access_token: str = ""
    resource_id: str = "volc.bigasr.auc_turbo"
    cluster: str = "volcengine_input_common"
    workflow: str = "audio_in,resample,partition,vad,fe,decode,itn,nlu_punctuate"
    boosting_table_name: str = ""
    timeout_s: int = 120
    system_prompt: str = (
        "你是专业中文转写纠错助手。修正错别字、口语重复、断句，保持原意，不要扩写。"
    )


class LLMConfig(BaseModel):
    base_url: str = "https://ark.cn-beijing.volces.com"
    api_key: str = ""
    model: str = "doubao-seed-2-0-pro-260215"
    timeout_s: int = 120
    temperature: float = 0.7
    script_system_prompt: str = (
        "你是短视频冷启动编剧专家。请基于给定转写文本生成荒诞、有趣、吸睛但合规的5秒前贴脚本，返回JSON。"
    )
    asr_polish_system_prompt: str = (
        "你是中文ASR文本纠错助手。只做纠错、断句和语义澄清，不要添加事实。"
    )


class VideoConfig(BaseModel):
    base_url: str = "https://ark.cn-beijing.volces.com"
    api_key: str = ""
    model: str = "seedance-1-5-pro-250528"
    timeout_s: int = 600
    poll_interval_s: int = 5
    system_prompt: str = (
        "生成荒诞、有趣、强视觉冲击的视频前贴，风格夸张、节奏快，适合短剧导流。"
    )


class PipelineConfig(BaseModel):
    default_asr_clip_seconds: int = 15
    default_hook_clip_seconds: int = 5
    enable_asr_polish: bool = True
    max_upload_mb: int = 300
    max_parallel_jobs: int = 1


class AppConfig(BaseModel):
    asr: ASRConfig = Field(default_factory=ASRConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)


class ConfigPresetSummary(BaseModel):
    name: str
    updated_at: str


class ConfigPresetOut(ConfigPresetSummary):
    config: AppConfig
