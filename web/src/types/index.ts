export type JobStatus =
  | "queued"
  | "preprocessing"
  | "asr"
  | "transcript_polish"
  | "script_gen"
  | "video_submit"
  | "video_polling"
  | "postprocess"
  | "completed"
  | "failed"
  | "canceled";

export type RerunStartStage =
  | "preprocessing"
  | "asr"
  | "transcript_polish"
  | "script_gen"
  | "video_submit"
  | "video_polling"
  | "postprocess";

export interface ASRConfig {
  base_url: string;
  appid: string;
  access_token: string;
  resource_id: string;
  cluster: string;
  workflow: string;
  boosting_table_name: string;
  timeout_s: number;
  system_prompt: string;
}

export interface LLMConfig {
  base_url: string;
  api_key: string;
  model: string;
  timeout_s: number;
  temperature: number;
  script_system_prompt: string;
  asr_polish_system_prompt: string;
}

export interface VideoConfig {
  base_url: string;
  api_key: string;
  model: string;
  timeout_s: number;
  poll_interval_s: number;
  system_prompt: string;
}

export interface PipelineConfig {
  default_asr_clip_seconds: number;
  default_hook_clip_seconds: number;
  enable_asr_polish: boolean;
  max_upload_mb: number;
  max_parallel_jobs: number;
}

export interface AppConfig {
  asr: ASRConfig;
  llm: LLMConfig;
  video: VideoConfig;
  pipeline: PipelineConfig;
}

export interface ConfigPresetSummary {
  name: string;
  updated_at: string;
}

export interface ConfigPreset {
  name: string;
  updated_at: string;
  config: AppConfig;
}

export interface JobOut {
  id: string;
  project_name: string;
  input_filename: string;
  source_path: string;
  asr_clip_seconds: number;
  hook_clip_seconds: number;
  status: JobStatus;
  error_message: string | null;
  artifacts: Record<string, string>;
  meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface JobEvent {
  id: number;
  job_id: string;
  status: JobStatus;
  message: string;
  created_at: string;
}

export interface JobCreateResponse {
  job_id: string;
  status: JobStatus;
}

export interface JobRerunRequest {
  start_stage: RerunStartStage;
  project_name?: string;
}

export interface HealthResponse {
  version: string;
  ffmpeg_available: boolean;
  ffprobe_available: boolean;
  queue_db: string;
  queued_jobs: number;
}
