import { AnimatePresence, motion } from "framer-motion";
import { BookmarkPlus, FolderOpen, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import type { AppConfig, ConfigPresetSummary } from "../types";

interface ConfigPanelProps {
  config: AppConfig;
  onChange: (next: AppConfig) => void;
  onSave: () => Promise<void>;
  saving: boolean;
  notice: string;
  presets: ConfigPresetSummary[];
  selectedPresetName: string;
  presetBusy: boolean;
  onSelectPreset: (name: string) => void;
  onSavePreset: (name: string) => Promise<void>;
  onLoadPreset: (name: string) => Promise<void>;
  onDeletePreset: (name: string) => Promise<void>;
}

function Field(props: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  multiline?: boolean;
  type?: string;
}) {
  const baseClass =
    "w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100 focus:border-ember focus:outline-none";

  return (
    <label className="flex flex-col gap-1 text-xs text-slate-300">
      <span>{props.label}</span>
      {props.multiline ? (
        <textarea
          className={`${baseClass} min-h-[86px] resize-y`}
          value={String(props.value)}
          onChange={(event) => props.onChange(event.target.value)}
        />
      ) : (
        <input
          className={baseClass}
          value={String(props.value)}
          type={props.type ?? "text"}
          onChange={(event) => props.onChange(event.target.value)}
        />
      )}
    </label>
  );
}

function ToggleField(props: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/25 px-3 py-2">
      <div>
        <p className="text-xs text-slate-100">{props.label}</p>
        <p className="text-[11px] text-slate-400">{props.description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={props.checked}
        onClick={() => props.onChange(!props.checked)}
        className={`relative h-6 w-11 rounded-full border transition ${
          props.checked
            ? "border-emerald-300/50 bg-emerald-400/25"
            : "border-white/20 bg-white/10"
        }`}
      >
        <span
          className={`absolute top-0.5 h-4.5 w-4.5 rounded-full bg-white shadow transition ${
            props.checked ? "left-5" : "left-1"
          }`}
        />
      </button>
    </div>
  );
}

export function ConfigPanel({
  config,
  onChange,
  onSave,
  saving,
  notice,
  presets,
  selectedPresetName,
  presetBusy,
  onSelectPreset,
  onSavePreset,
  onLoadPreset,
  onDeletePreset
}: ConfigPanelProps) {
  const [presetDraftName, setPresetDraftName] = useState("");

  useEffect(() => {
    if (selectedPresetName) {
      setPresetDraftName(selectedPresetName);
    }
  }, [selectedPresetName]);

  const patch = <T extends keyof AppConfig>(section: T, key: keyof AppConfig[T], value: string | boolean) => {
    const next = structuredClone(config);
    const currentValue = next[section][key];
    const mutableSection = next[section] as unknown as Record<string, unknown>;

    if (typeof currentValue === "number") {
      mutableSection[key as string] = Number(value);
    } else if (typeof currentValue === "boolean") {
      mutableSection[key as string] = Boolean(value);
    } else {
      mutableSection[key as string] = String(value);
    }

    onChange(next);
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className="panel-card h-full overflow-hidden"
    >
      <header className="mb-4 flex items-center justify-between">
        <div>
          <p className="font-display text-sm uppercase tracking-[0.3em] text-ember/80">Model Config</p>
          <h2 className="font-display text-xl text-white">模型与 Prompt 控制台</h2>
        </div>
        <button
          onClick={() => {
            void onSave();
          }}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-xl border border-ember/60 bg-ember/20 px-4 py-2 text-sm font-medium text-white transition hover:bg-ember/30 disabled:opacity-60"
        >
          <Save className="h-4 w-4" />
          {saving ? "保存中..." : "保存配置"}
        </button>
      </header>

      <div className="mb-3 rounded-xl border border-white/10 bg-black/25 p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="font-display text-xs uppercase tracking-[0.18em] text-calm/90">配置预设</p>
          <span className="text-[11px] text-slate-400">{presets.length} saved</span>
        </div>

        <div className="grid gap-2">
          <select
            className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100 focus:border-calm focus:outline-none"
            value={selectedPresetName}
            onChange={(event) => onSelectPreset(event.target.value)}
          >
            <option value="">选择已保存预设</option>
            {presets.map((preset) => (
              <option key={preset.name} value={preset.name}>
                {preset.name}
              </option>
            ))}
          </select>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => {
                void onLoadPreset(selectedPresetName);
              }}
              disabled={presetBusy || !selectedPresetName}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-calm/45 bg-calm/10 px-3 py-2 text-xs text-calm transition hover:bg-calm/15 disabled:opacity-50"
            >
              <FolderOpen className="h-3.5 w-3.5" />
              {presetBusy ? "处理中..." : "切换预设"}
            </button>
            <button
              onClick={() => {
                void onDeletePreset(selectedPresetName);
              }}
              disabled={presetBusy || !selectedPresetName}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-400/45 bg-red-500/10 px-3 py-2 text-xs text-red-200 transition hover:bg-red-500/15 disabled:opacity-50"
            >
              <Trash2 className="h-3.5 w-3.5" />
              删除预设
            </button>
          </div>

          <div className="flex gap-2">
            <input
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100 focus:border-ember focus:outline-none"
              placeholder="输入预设名（如：seed2-prod）"
              value={presetDraftName}
              onChange={(event) => setPresetDraftName(event.target.value)}
            />
            <button
              onClick={() => {
                void onSavePreset(presetDraftName);
              }}
              disabled={presetBusy || !presetDraftName.trim()}
              className="inline-flex items-center gap-2 rounded-xl border border-ember/50 bg-ember/15 px-3 py-2 text-xs text-white transition hover:bg-ember/25 disabled:opacity-50"
            >
              <BookmarkPlus className="h-3.5 w-3.5" />
              保存预设
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-4 overflow-y-auto pr-1 text-sm max-h-[calc(100vh-220px)]">
        <details open className="cfg-group">
          <summary>ASR · 豆包 ASR 2.0</summary>
          <div className="cfg-grid">
            <Field label="Base URL" value={config.asr.base_url} onChange={(v) => patch("asr", "base_url", v)} />
            <Field label="AppID" value={config.asr.appid} onChange={(v) => patch("asr", "appid", v)} />
            <Field
              label="Access Token"
              value={config.asr.access_token}
              onChange={(v) => patch("asr", "access_token", v)}
              type="password"
            />
            <Field label="Resource ID" value={config.asr.resource_id} onChange={(v) => patch("asr", "resource_id", v)} />
            <Field label="Cluster" value={config.asr.cluster} onChange={(v) => patch("asr", "cluster", v)} />
            <Field label="Workflow" value={config.asr.workflow} onChange={(v) => patch("asr", "workflow", v)} />
            <Field
              label="Boosting Table"
              value={config.asr.boosting_table_name}
              onChange={(v) => patch("asr", "boosting_table_name", v)}
            />
            <Field label="Timeout(s)" value={config.asr.timeout_s} onChange={(v) => patch("asr", "timeout_s", v)} />
          </div>
          <Field
            label="ASR System Prompt（纠错步骤）"
            value={config.asr.system_prompt}
            onChange={(v) => patch("asr", "system_prompt", v)}
            multiline
          />
        </details>

        <details open className="cfg-group">
          <summary>LLM · Seed-2.0-Pro</summary>
          <div className="cfg-grid">
            <Field label="Base URL" value={config.llm.base_url} onChange={(v) => patch("llm", "base_url", v)} />
            <Field label="API Key" value={config.llm.api_key} onChange={(v) => patch("llm", "api_key", v)} type="password" />
            <Field label="Model" value={config.llm.model} onChange={(v) => patch("llm", "model", v)} />
            <Field label="Timeout(s)" value={config.llm.timeout_s} onChange={(v) => patch("llm", "timeout_s", v)} />
            <Field
              label="Temperature"
              value={config.llm.temperature}
              onChange={(v) => patch("llm", "temperature", v)}
            />
          </div>
          <Field
            label="Script System Prompt"
            value={config.llm.script_system_prompt}
            onChange={(v) => patch("llm", "script_system_prompt", v)}
            multiline
          />
          <Field
            label="ASR Polish System Prompt"
            value={config.llm.asr_polish_system_prompt}
            onChange={(v) => patch("llm", "asr_polish_system_prompt", v)}
            multiline
          />
        </details>

        <details open className="cfg-group">
          <summary>Video · Seedance 1.5 Pro</summary>
          <div className="cfg-grid">
            <Field label="Base URL" value={config.video.base_url} onChange={(v) => patch("video", "base_url", v)} />
            <Field
              label="API Key"
              value={config.video.api_key}
              onChange={(v) => patch("video", "api_key", v)}
              type="password"
            />
            <Field label="Model" value={config.video.model} onChange={(v) => patch("video", "model", v)} />
            <Field label="Timeout(s)" value={config.video.timeout_s} onChange={(v) => patch("video", "timeout_s", v)} />
            <Field
              label="Poll Interval(s)"
              value={config.video.poll_interval_s}
              onChange={(v) => patch("video", "poll_interval_s", v)}
            />
          </div>
          <Field
            label="Video System Prompt"
            value={config.video.system_prompt}
            onChange={(v) => patch("video", "system_prompt", v)}
            multiline
          />
        </details>

        <details open className="cfg-group">
          <summary>Pipeline Defaults</summary>
          <div className="mb-3">
            <ToggleField
              label="启用 ASR 文本纠错"
              description="关闭后将直接使用 ASR 原始转写进入脚本生成，可减少延迟与成本。"
              checked={config.pipeline.enable_asr_polish}
              onChange={(checked) => patch("pipeline", "enable_asr_polish", checked)}
            />
          </div>
          <div className="cfg-grid">
            <Field
              label="ASR Clip Seconds"
              value={config.pipeline.default_asr_clip_seconds}
              onChange={(v) => patch("pipeline", "default_asr_clip_seconds", v)}
            />
            <Field
              label="Hook Clip Seconds"
              value={config.pipeline.default_hook_clip_seconds}
              onChange={(v) => patch("pipeline", "default_hook_clip_seconds", v)}
            />
            <Field
              label="Max Upload(MB)"
              value={config.pipeline.max_upload_mb}
              onChange={(v) => patch("pipeline", "max_upload_mb", v)}
            />
            <Field
              label="Max Parallel Jobs"
              value={config.pipeline.max_parallel_jobs}
              onChange={(v) => patch("pipeline", "max_parallel_jobs", v)}
            />
          </div>
        </details>
      </div>

      <AnimatePresence>
        {notice ? (
          <motion.p
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className="mt-3 rounded-lg border border-calm/40 bg-calm/10 px-3 py-2 text-xs text-calm"
          >
            {notice}
          </motion.p>
        ) : null}
      </AnimatePresence>
    </motion.section>
  );
}
