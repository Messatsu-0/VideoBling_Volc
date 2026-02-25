import { motion } from "framer-motion";
import { Clapperboard, PlayCircle, Upload } from "lucide-react";
import { useMemo, useState } from "react";

interface WorkspacePanelProps {
  defaultAsrSeconds: number;
  defaultHookSeconds: number;
  onRun: (payload: { videoFile: File; projectName: string; asrClipSeconds: number; hookClipSeconds: number }) => Promise<void>;
  running: boolean;
}

export function WorkspacePanel({ defaultAsrSeconds, defaultHookSeconds, onRun, running }: WorkspacePanelProps) {
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [projectName, setProjectName] = useState("");
  const [asrClipSeconds, setAsrClipSeconds] = useState(defaultAsrSeconds);
  const [hookClipSeconds, setHookClipSeconds] = useState(defaultHookSeconds);

  const previewUrl = useMemo(() => {
    if (!videoFile) {
      return "";
    }
    return URL.createObjectURL(videoFile);
  }, [videoFile]);

  const canRun = Boolean(videoFile) && !running;

  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1, duration: 0.65, ease: "easeOut" }}
      className="panel-card h-full"
    >
      <header className="mb-4">
        <p className="font-display text-sm uppercase tracking-[0.3em] text-flare/80">Workflow</p>
        <h2 className="font-display text-xl text-white">上传并运行 AI 前贴流水线</h2>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="col-span-2 rounded-2xl border border-dashed border-white/30 bg-white/[0.02] px-4 py-6 text-center transition hover:border-ember/70 hover:bg-ember/5">
          <input
            type="file"
            accept="video/*"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              setVideoFile(file);
              if (file && !projectName) {
                setProjectName(file.name.replace(/\.[^.]+$/, ""));
              }
            }}
          />
          <div className="flex flex-col items-center gap-2">
            <Upload className="h-7 w-7 text-ember" />
            <p className="text-sm text-slate-200">点击上传原始完整视频</p>
            <p className="text-xs text-slate-400">支持 MP4/MOV，上传后会自动排入异步队列</p>
            {videoFile ? <p className="font-mono text-xs text-calm">{videoFile.name}</p> : null}
          </div>
        </label>

        <label className="field">
          <span>项目名称</span>
          <input value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="短剧引流计划" />
        </label>

        <label className="field">
          <span>ASR 截取秒数</span>
          <input
            type="number"
            min={1}
            max={120}
            value={asrClipSeconds}
            onChange={(e) => setAsrClipSeconds(Number(e.target.value))}
          />
        </label>

        <label className="field">
          <span>前贴时长(秒)</span>
          <input
            type="number"
            min={1}
            max={20}
            value={hookClipSeconds}
            onChange={(e) => setHookClipSeconds(Number(e.target.value))}
          />
        </label>

        <button
          className="run-btn"
          disabled={!canRun}
          onClick={() => {
            if (!videoFile) {
              return;
            }
            void onRun({
              videoFile,
              projectName,
              asrClipSeconds,
              hookClipSeconds
            });
          }}
        >
          <PlayCircle className="h-5 w-5" />
          {running ? "任务提交中..." : "启动 AI 前贴流水线"}
        </button>
      </div>

      <div className="mt-5 rounded-2xl border border-white/10 bg-black/30 p-3">
        <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.25em] text-slate-400">
          <Clapperboard className="h-4 w-4" />
          源视频预览
        </div>
        {previewUrl ? (
          <video src={previewUrl} controls className="h-[300px] w-full rounded-xl object-contain bg-black/70" />
        ) : (
          <div className="flex h-[300px] items-center justify-center rounded-xl border border-dashed border-white/10 text-sm text-slate-500">
            上传后可预览
          </div>
        )}
      </div>
    </motion.section>
  );
}
