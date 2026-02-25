import type {
  AppConfig,
  ConfigPreset,
  ConfigPresetSummary,
  HealthResponse,
  JobCreateResponse,
  JobOut,
  JobRerunRequest
} from "../types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return null as T;
  }
  return (await response.json()) as T;
}

export function getHealth() {
  return request<HealthResponse>("/api/health");
}

export function getConfig() {
  return request<AppConfig>("/api/config");
}

export function saveConfig(payload: AppConfig) {
  return request<AppConfig>("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function listConfigPresets() {
  return request<ConfigPresetSummary[]>("/api/config/presets");
}

export function getConfigPreset(name: string) {
  return request<ConfigPreset>(`/api/config/presets/${encodeURIComponent(name)}`);
}

export function saveConfigPreset(name: string, payload: AppConfig) {
  return request<ConfigPreset>(`/api/config/presets/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function deleteConfigPreset(name: string) {
  return request<{ deleted: boolean; name: string }>(`/api/config/presets/${encodeURIComponent(name)}`, {
    method: "DELETE"
  });
}

export function listJobs() {
  return request<JobOut[]>("/api/jobs");
}

export function getJob(jobId: string) {
  return request<JobOut>(`/api/jobs/${jobId}`);
}

export function deleteJob(jobId: string, force = true) {
  const query = force ? "?force=true" : "";
  return request<{ deleted: boolean; job_id: string; force: boolean }>(`/api/jobs/${jobId}${query}`, {
    method: "DELETE"
  });
}

export function rerunJob(jobId: string, payload: JobRerunRequest) {
  return request<JobCreateResponse>(`/api/jobs/${jobId}/rerun`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function createJob(input: {
  videoFile: File;
  projectName: string;
  asrClipSeconds: number;
  hookClipSeconds: number;
}) {
  const form = new FormData();
  form.append("video_file", input.videoFile);
  form.append("project_name", input.projectName);
  form.append("asr_clip_seconds", String(input.asrClipSeconds));
  form.append("hook_clip_seconds", String(input.hookClipSeconds));

  return request<JobCreateResponse>("/api/jobs", {
    method: "POST",
    body: form
  });
}

export function cleanupJobs(keepLatest = 20) {
  return request<{ removed: string[]; keep_latest: number }>(`/api/jobs/cleanup?keep_latest=${keepLatest}`, {
    method: "POST"
  });
}

export function artifactUrl(jobId: string, kind: string) {
  return `/api/jobs/${jobId}/artifacts/${kind}`;
}
