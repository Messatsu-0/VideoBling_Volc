import { gsap } from "gsap";
import { AnimatePresence, motion } from "framer-motion";
import { Sparkles, WandSparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  cleanupJobs,
  createJob,
  deleteJob,
  deleteConfigPreset,
  getConfig,
  getConfigPreset,
  getHealth,
  listConfigPresets,
  listJobs,
  rerunJob,
  saveConfig,
  saveConfigPreset
} from "./api/client";
import { ConfigPanel } from "./components/ConfigPanel";
import { QueuePanel } from "./components/QueuePanel";
import { WorkspacePanel } from "./components/WorkspacePanel";
import { useJobEvents } from "./hooks/useJobEvents";
import type { AppConfig, ConfigPresetSummary, JobEvent, JobOut, RerunStartStage } from "./types";

function App() {
  const backgroundRef = useRef<HTMLDivElement | null>(null);

  const [config, setConfig] = useState<AppConfig | null>(null);
  const [jobs, setJobs] = useState<JobOut[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [eventsByJob, setEventsByJob] = useState<Record<string, JobEvent[]>>({});
  const [configPresets, setConfigPresets] = useState<ConfigPresetSummary[]>([]);
  const [selectedPresetName, setSelectedPresetName] = useState("");
  const [savingConfig, setSavingConfig] = useState(false);
  const [presetBusy, setPresetBusy] = useState(false);
  const [submittingJob, setSubmittingJob] = useState(false);
  const [rerunPendingJobId, setRerunPendingJobId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");

  const selectedJobEvents = useMemo(() => {
    if (!selectedJobId) {
      return [];
    }
    return eventsByJob[selectedJobId] ?? [];
  }, [eventsByJob, selectedJobId]);

  const refreshJobs = useCallback(async () => {
    const nextJobs = await listJobs();
    setJobs(nextJobs);
    if (selectedJobId && !nextJobs.some((job) => job.id === selectedJobId)) {
      setSelectedJobId(null);
    }
  }, [selectedJobId]);

  const refreshPresets = useCallback(async () => {
    const nextPresets = await listConfigPresets();
    setConfigPresets(nextPresets);
    setSelectedPresetName((prev) => {
      if (prev && nextPresets.some((item) => item.name === prev)) {
        return prev;
      }
      return nextPresets[0]?.name ?? "";
    });
  }, []);

  const bootstrap = useCallback(async () => {
    const [cfg, jobList, health, presets] = await Promise.all([getConfig(), listJobs(), getHealth(), listConfigPresets()]);
    setConfig(cfg);
    setJobs(jobList);
    setConfigPresets(presets);
    setSelectedPresetName(presets[0]?.name ?? "");
    if (!health.ffmpeg_available || !health.ffprobe_available) {
      setNotice("检测到 ffmpeg/ffprobe 不可用，请先安装后再运行任务。");
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshJobs();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [refreshJobs]);

  useEffect(() => {
    if (!backgroundRef.current) {
      return;
    }

    const timeline = gsap.timeline({ repeat: -1, yoyo: true });
    timeline
      .to(".orb-a", { x: 18, y: -14, duration: 4.2, ease: "sine.inOut" })
      .to(".orb-b", { x: -24, y: 14, duration: 5.4, ease: "sine.inOut" }, 0)
      .to(".orb-c", { x: 8, y: 20, duration: 6.8, ease: "sine.inOut" }, 0);

    return () => {
      timeline.kill();
    };
  }, []);

  useEffect(() => {
    if (!notice) {
      return;
    }
    const timer = window.setTimeout(() => setNotice(""), 4200);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const handleSseEvent = useCallback((event: JobEvent) => {
    setEventsByJob((prev) => {
      const next = { ...prev };
      const existing = next[event.job_id] ?? [];
      if (existing.some((item) => item.id === event.id)) {
        return prev;
      }
      next[event.job_id] = [...existing, event].slice(-200);
      return next;
    });
    void refreshJobs();
  }, [refreshJobs]);

  useJobEvents({
    jobId: selectedJobId,
    onEvent: handleSseEvent,
    onEnd: () => {
      void refreshJobs();
    }
  });

  const handleSaveConfig = useCallback(async () => {
    if (!config) {
      return;
    }
    setSavingConfig(true);
    try {
      const next = await saveConfig(config);
      setConfig(next);
      setNotice("配置保存成功（明文本地复用）。");
    } catch (error) {
      setNotice(`配置保存失败：${String(error)}`);
    } finally {
      setSavingConfig(false);
    }
  }, [config]);

  const handleSavePreset = useCallback(
    async (presetName: string) => {
      if (!config) {
        return;
      }
      const name = presetName.trim();
      if (!name) {
        setNotice("请输入预设名称后再保存。");
        return;
      }
      setPresetBusy(true);
      try {
        await saveConfigPreset(name, config);
        setSelectedPresetName(name);
        await refreshPresets();
        setNotice(`预设已保存：${name}`);
      } catch (error) {
        setNotice(`预设保存失败：${String(error)}`);
      } finally {
        setPresetBusy(false);
      }
    },
    [config, refreshPresets]
  );

  const handleLoadPreset = useCallback(async (presetName: string) => {
    const name = presetName.trim();
    if (!name) {
      setNotice("请先选择一个预设。");
      return;
    }
    setPresetBusy(true);
    try {
      const preset = await getConfigPreset(name);
      const next = await saveConfig(preset.config);
      setConfig(next);
      setSelectedPresetName(preset.name);
      setNotice(`已切换并加载预设：${preset.name}`);
    } catch (error) {
      setNotice(`预设加载失败：${String(error)}`);
    } finally {
      setPresetBusy(false);
    }
  }, []);

  const handleDeletePreset = useCallback(
    async (presetName: string) => {
      const name = presetName.trim();
      if (!name) {
        setNotice("请先选择要删除的预设。");
        return;
      }
      setPresetBusy(true);
      try {
        await deleteConfigPreset(name);
        await refreshPresets();
        setNotice(`预设已删除：${name}`);
      } catch (error) {
        setNotice(`预设删除失败：${String(error)}`);
      } finally {
        setPresetBusy(false);
      }
    },
    [refreshPresets]
  );

  const handleRunJob = useCallback(
    async (payload: { videoFile: File; projectName: string; asrClipSeconds: number; hookClipSeconds: number }) => {
      setSubmittingJob(true);
      try {
        const response = await createJob(payload);
        setSelectedJobId(response.job_id);
        setNotice(`任务已提交：${response.job_id}`);
        await refreshJobs();
      } catch (error) {
        setNotice(`任务提交失败：${String(error)}`);
      } finally {
        setSubmittingJob(false);
      }
    },
    [refreshJobs]
  );

  const handleCleanup = useCallback(async () => {
    try {
      const result = await cleanupJobs(20);
      setNotice(`已清理 ${result.removed.length} 个历史任务目录`);
      await refreshJobs();
    } catch (error) {
      setNotice(`清理失败：${String(error)}`);
    }
  }, [refreshJobs]);

  const handleDeleteJob = useCallback(
    async (jobId: string) => {
      try {
        await deleteJob(jobId, true);
        setSelectedJobId((prev) => (prev === jobId ? null : prev));
        setEventsByJob((prev) => {
          const next = { ...prev };
          delete next[jobId];
          return next;
        });
        setNotice(`任务已删除：${jobId}`);
        await refreshJobs();
      } catch (error) {
        setNotice(`删除任务失败：${String(error)}`);
      }
    },
    [refreshJobs]
  );

  const handleRerunJob = useCallback(
    async (jobId: string, startStage: RerunStartStage) => {
      setRerunPendingJobId(jobId);
      try {
        const response = await rerunJob(jobId, { start_stage: startStage });
        setSelectedJobId(response.job_id);
        setNotice(`已创建重跑任务：${response.job_id}（起点：${startStage}）`);
        await refreshJobs();
      } catch (error) {
        setNotice(`重跑任务创建失败：${String(error)}`);
      } finally {
        setRerunPendingJobId(null);
      }
    },
    [refreshJobs]
  );

  if (!config) {
    return (
      <div className="loading-shell">
        <div className="loader" />
        <p>Loading VideoBling Local Studio...</p>
      </div>
    );
  }

  return (
    <div ref={backgroundRef} className="min-h-screen bg-ink text-white">
      <div className="bg-orb orb-a" />
      <div className="bg-orb orb-b" />
      <div className="bg-orb orb-c" />

      <main className="mx-auto max-w-[1680px] px-4 py-4 sm:px-6 lg:px-8 lg:py-7">
        <motion.header
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-5 flex flex-col justify-between gap-3 rounded-2xl border border-white/10 bg-black/30 p-4 backdrop-blur-xl lg:flex-row lg:items-center"
        >
          <div>
            <p className="font-display text-xs uppercase tracking-[0.34em] text-ember/80">Cinematic Neon Lab</p>
            <h1 className="mt-1 font-display text-2xl leading-tight text-white sm:text-3xl">
              VideoBling Local Studio
              <span className="ml-2 inline-flex items-center gap-1 rounded-full border border-ember/40 bg-ember/10 px-2 py-0.5 text-xs text-ember">
                <Sparkles className="h-3 w-3" />
                Seed Pipeline
              </span>
            </h1>
          </div>
          <p className="max-w-xl text-sm text-slate-300">
            上传原视频后，系统将按你的 Prompt 调用豆包 ASR 2.0、Seed-2.0-Pro 与 Seedance 1.5 Pro 自动生成荒诞吸睛前贴并拼接成片。
          </p>
        </motion.header>

        <AnimatePresence>
          {notice ? (
            <motion.div
              initial={{ opacity: 0, y: -12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.98 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="fixed left-1/2 top-4 z-[90] w-[min(900px,92vw)] -translate-x-1/2 cursor-pointer rounded-xl border border-ember/45 bg-ember/15 px-4 py-3 text-sm text-amber-100 shadow-[0_12px_38px_rgba(255,45,85,0.28)] backdrop-blur-sm"
              onClick={() => setNotice("")}
              role="status"
              aria-live="polite"
            >
              {notice}
            </motion.div>
          ) : null}
        </AnimatePresence>

        <div className="grid gap-4 xl:grid-cols-[1.15fr_1fr_1fr]">
          <ConfigPanel
            config={config}
            onChange={setConfig}
            onSave={handleSaveConfig}
            saving={savingConfig}
            notice=""
            presets={configPresets}
            selectedPresetName={selectedPresetName}
            presetBusy={presetBusy}
            onSelectPreset={setSelectedPresetName}
            onSavePreset={handleSavePreset}
            onLoadPreset={handleLoadPreset}
            onDeletePreset={handleDeletePreset}
          />
          <WorkspacePanel
            defaultAsrSeconds={config.pipeline.default_asr_clip_seconds}
            defaultHookSeconds={config.pipeline.default_hook_clip_seconds}
            onRun={handleRunJob}
            running={submittingJob}
          />
          <QueuePanel
            jobs={jobs}
            selectedJobId={selectedJobId}
            onSelectJob={setSelectedJobId}
            events={selectedJobEvents}
            onDeleteJob={handleDeleteJob}
            onRerunJob={handleRerunJob}
            rerunPendingJobId={rerunPendingJobId}
            onRefresh={refreshJobs}
            onCleanup={handleCleanup}
          />
        </div>

        <footer className="mt-4 flex items-center justify-end text-xs text-slate-500">
          <WandSparkles className="mr-2 h-3.5 w-3.5" />
          Local-first MVP · React + FastAPI + SQLite Queue
        </footer>
      </main>
    </div>
  );
}

export default App;
