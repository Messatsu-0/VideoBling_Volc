import { AnimatePresence, motion } from "framer-motion";
import { Download, RefreshCcw, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { artifactUrl } from "../api/client";
import type { JobEvent, JobOut, RerunStartStage } from "../types";

const STAGE_ORDER = [
  "queued",
  "preprocessing",
  "asr",
  "transcript_polish",
  "script_gen",
  "video_submit",
  "video_polling",
  "postprocess",
  "completed"
] as const;

const RERUN_STAGES: Array<{ value: RerunStartStage; label: string }> = [
  { value: "preprocessing", label: "preprocessing · 预处理" },
  { value: "asr", label: "asr · 音频截取与识别" },
  { value: "transcript_polish", label: "transcript_polish · 文本纠错" },
  { value: "script_gen", label: "script_gen · 脚本生成" },
  { value: "video_submit", label: "video_submit · 提交生视频任务" },
  { value: "video_polling", label: "video_polling · 轮询下载视频" },
  { value: "postprocess", label: "postprocess · 拼接导出" }
];

function statusClass(status: string): string {
  if (status === "completed") {
    return "text-emerald-300 border-emerald-500/40 bg-emerald-500/10";
  }
  if (status === "failed") {
    return "text-rose-300 border-rose-500/40 bg-rose-500/10";
  }
  return "text-calm border-calm/30 bg-calm/10";
}

function progressValue(status: string): number {
  const index = STAGE_ORDER.findIndex((item) => item === status);
  if (index < 0) {
    return status === "failed" ? 100 : 0;
  }
  return Math.round(((index + 1) / STAGE_ORDER.length) * 100);
}

interface QueuePanelProps {
  jobs: JobOut[];
  selectedJobId: string | null;
  onSelectJob: (jobId: string | null) => void;
  events: JobEvent[];
  onDeleteJob: (jobId: string) => Promise<void>;
  onRerunJob: (jobId: string, startStage: RerunStartStage) => Promise<void>;
  rerunPendingJobId: string | null;
  onRefresh: () => Promise<void>;
  onCleanup: () => Promise<void>;
}

function statusToRerunStage(status: string): RerunStartStage {
  const found = RERUN_STAGES.find((item) => item.value === status);
  return found ? found.value : "preprocessing";
}

export function QueuePanel({
  jobs,
  selectedJobId,
  onSelectJob,
  events,
  onDeleteJob,
  onRerunJob,
  rerunPendingJobId,
  onRefresh,
  onCleanup
}: QueuePanelProps) {
  const selected = jobs.find((job) => job.id === selectedJobId) ?? null;
  const [rerunStage, setRerunStage] = useState<RerunStartStage>("preprocessing");

  useEffect(() => {
    if (!selected) {
      setRerunStage("preprocessing");
      return;
    }
    setRerunStage(statusToRerunStage(selected.status));
  }, [selected?.id, selected?.status]);

  return (
    <motion.section
      initial={{ opacity: 0, y: 28 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.72, ease: "easeOut" }}
      className="panel-card h-full overflow-visible"
    >
      <header className="mb-4 flex items-center justify-between">
        <div>
          <p className="font-display text-sm uppercase tracking-[0.3em] text-calm/80">Queue</p>
          <h2 className="font-display text-xl text-white">异步任务与产物</h2>
        </div>
        <div className="flex gap-2">
          <button className="icon-btn" onClick={() => void onRefresh()}>
            <RefreshCcw className="h-4 w-4" />
          </button>
          <button className="icon-btn" onClick={() => void onCleanup()}>
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </header>

      <p className="mb-3 text-xs text-slate-400">点击任意任务，弹出宽屏详情窗口。点击空白区域即可关闭。</p>

      <div className="min-w-0 max-h-[560px] space-y-3 overflow-y-auto pr-1">
        {jobs.length === 0 ? (
          <div className="rounded-xl border border-dashed border-white/20 p-4 text-sm text-slate-400">暂无任务</div>
        ) : null}
        {jobs.map((job) => (
          <button
            key={job.id}
            onClick={() => onSelectJob(job.id)}
            className={`w-full rounded-xl border px-3 py-3 text-left transition ${
              selected?.id === job.id ? "border-ember/70 bg-ember/10" : "border-white/10 bg-white/[0.02] hover:border-white/25"
            }`}
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="truncate font-medium text-white">{job.project_name}</p>
              <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase ${statusClass(job.status)}`}>{job.status}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
              <div style={{ width: `${progressValue(job.status)}%` }} className="h-full bg-gradient-to-r from-calm to-ember" />
            </div>
            <p className="mt-2 break-all font-mono text-[11px] text-slate-400">{job.id}</p>
          </button>
        ))}
      </div>

      <AnimatePresence>
        {selected ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[70] bg-black/60 backdrop-blur-[2px]"
            onClick={() => onSelectJob(null)}
          >
            <motion.div
              initial={{ opacity: 0, y: 28, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.98 }}
              transition={{ duration: 0.24, ease: "easeOut" }}
              className="mx-auto mt-[6vh] flex max-h-[88vh] w-[min(1100px,94vw)] flex-col rounded-2xl border border-white/15 bg-[#090d14]/95 shadow-[0_30px_100px_rgba(0,0,0,0.6)]"
              onClick={(event) => event.stopPropagation()}
            >
              <header className="flex items-start justify-between gap-3 border-b border-white/10 px-4 py-3">
                <div className="min-w-0">
                  <h3 className="truncate font-display text-2xl text-white">{selected.project_name}</h3>
                  <p className="mt-1 break-all font-mono text-xs text-slate-400">{selected.id}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    className="icon-btn border-rose-400/40 bg-rose-500/10 text-rose-200 hover:bg-rose-500/20"
                    onClick={() => {
                      void onDeleteJob(selected.id);
                    }}
                    aria-label="删除任务"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase ${statusClass(selected.status)}`}>
                    {selected.status}
                  </span>
                  <button className="icon-btn" onClick={() => onSelectJob(null)} aria-label="关闭详情弹窗">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </header>

              <div className="grid min-h-0 flex-1 gap-4 overflow-hidden p-4 lg:grid-cols-[1.15fr_1fr]">
                <div className="min-w-0 space-y-3 overflow-y-auto pr-1">
                  {selected.error_message ? (
                    <p className="break-all rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                      {selected.error_message}
                    </p>
                  ) : (
                    <p className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
                      当前任务无报错，可查看产物与实时日志。
                    </p>
                  )}

                  <div className="rounded-xl border border-white/10 bg-black/40 p-3">
                    <p className="mb-2 font-display text-xs uppercase tracking-[0.28em] text-slate-400">产物下载</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.keys(selected.artifacts).length === 0 ? (
                        <p className="text-xs text-slate-500">暂无产物</p>
                      ) : (
                        Object.keys(selected.artifacts).map((kind) => (
                          <a key={kind} href={artifactUrl(selected.id, kind)} target="_blank" rel="noreferrer" className="artifact-link">
                            <Download className="h-3.5 w-3.5" />
                            {kind}
                          </a>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="rounded-xl border border-white/10 bg-black/40 p-3">
                    <p className="mb-2 font-display text-xs uppercase tracking-[0.28em] text-slate-400">从任意阶段重跑</p>
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <select
                        className="w-full rounded-lg border border-white/15 bg-[#0a1019] px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-ember/60"
                        value={rerunStage}
                        onChange={(event) => setRerunStage(event.target.value as RerunStartStage)}
                      >
                        {RERUN_STAGES.map((stage) => (
                          <option key={stage.value} value={stage.value}>
                            {stage.label}
                          </option>
                        ))}
                      </select>
                      <button
                        className="rounded-lg border border-ember/40 bg-ember/15 px-3 py-2 text-sm font-medium text-amber-100 transition hover:bg-ember/25 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={rerunPendingJobId === selected.id}
                        onClick={() => {
                          void onRerunJob(selected.id, rerunStage);
                        }}
                      >
                        {rerunPendingJobId === selected.id ? "提交中..." : "从该阶段重跑"}
                      </button>
                    </div>
                    <p className="mt-2 text-[11px] text-slate-500">将新建任务并复用该阶段之前的中间产物。</p>
                  </div>
                </div>

                <div className="rounded-xl border border-white/10 bg-black/40 p-3">
                  <p className="mb-2 font-display text-xs uppercase tracking-[0.28em] text-slate-400">实时日志</p>
                  <div className="max-h-[56vh] space-y-2 overflow-y-auto pr-1 font-mono text-xs text-slate-300">
                    {events.length === 0 ? (
                      <p className="text-slate-500">等待日志...</p>
                    ) : (
                      events.map((event) => (
                        <div key={event.id} className="rounded-lg border border-white/10 bg-white/[0.02] px-2 py-1.5">
                          <div className="mb-1 flex items-center justify-between text-[10px] text-slate-500">
                            <span>{event.status}</span>
                            <span>{new Date(event.created_at).toLocaleTimeString()}</span>
                          </div>
                          <p className="break-words">{event.message}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.section>
  );
}
