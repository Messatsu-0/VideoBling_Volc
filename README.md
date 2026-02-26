# VideoBling Local (MVP)

本项目实现本机可运行的完整链路：

1. 上传完整原视频
2. 截取前 N 秒做 ASR（豆包 ASR 2.0）
3. 用 Seed-2.0-Pro 做 ASR 文本纠错（ASR system prompt 生效点）
4. 用 Seed-2.0-Pro 生成荒诞吸睛前贴脚本（结构化 JSON）
5. 调用 Seedance 1.5 Pro 生 5 秒前贴
6. 将前贴标准化后拼接到原始完整视频最前
7. 输出成片

## 目录

- `backend/` FastAPI + SQLAlchemy + Huey + ffmpeg pipeline
- `web/` React + Vite + Tailwind + Framer Motion + GSAP
- `runtime/` 本地运行数据（配置、队列、任务产物）
- `tests/` 单测/集成/e2e 占位

## 已实现接口

- `GET /api/health`
- `GET /api/config`
- `PUT /api/config`
- `GET /api/config/presets`
- `GET /api/config/presets/{preset_name}`
- `PUT /api/config/presets/{preset_name}`
- `DELETE /api/config/presets/{preset_name}`
- `POST /api/jobs` (multipart/form-data)
- `POST /api/jobs/{job_id}/rerun` (JSON: `start_stage`, `project_name?`)
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `DELETE /api/jobs/{job_id}` (`force=true` 可删除非终态任务)
- `GET /api/jobs/{job_id}/events` (SSE)
- `GET /api/jobs/{job_id}/artifacts/{kind}`
- `POST /api/jobs/cleanup`

支持的 artifact kind:

- `source_video`
- `asr_clip_audio`
- `transcript_raw`
- `transcript_polished`
- `hook_script_json`
- `hook_video_raw`
- `hook_video_norm`
- `final_video`

## Docker 一键运行（推荐）

如果你希望完全在容器里跑，不依赖本机 Node/Python/ffmpeg：

### 前置

- Docker Desktop（或 Docker Engine + Compose）

### 启动

```bash
cd /Users/bytedance/Documents/VideoBling_local
./scripts/start_docker.sh
```

打开：

- Web: `http://localhost:5173`
- API Health: `http://localhost:18000/api/health`

### 停止

```bash
cd /Users/bytedance/Documents/VideoBling_local
./scripts/stop_docker.sh
```

### 容器说明

- `backend`：FastAPI API 服务（内置 ffmpeg/ffprobe）
- `worker`：Huey 异步任务执行器
- `web`：Vite React 前端
- 运行数据持久化到宿主机 `runtime/`

## 公网部署（ECS + 公网IP）

如果你要让外部客户访问（非 Tailscale 方案），请使用生产编排与网关：

1. 生产 Compose：`/Users/bytedance/Documents/VideoBling_local/docker-compose.prod.yml`
2. 网关配置：`/Users/bytedance/Documents/VideoBling_local/deploy/gateway/nginx.conf`
3. 部署脚本：
   - `./scripts/deploy_prod.sh`
   - `./scripts/update_prod.sh`
   - `./scripts/rollback_prod.sh`
   - `./scripts/init_ecs_ubuntu.sh`
   - `./scripts/print_access_url.sh`
4. 详细步骤见：`/Users/bytedance/Documents/VideoBling_local/DEPLOYMENT_CN.md`

### GitHub Actions 自动发布（可选，推荐）

仓库已内置工作流：

- `/Users/bytedance/Documents/VideoBling_local/.github/workflows/deploy-ecs.yml`

作用：

1. 推送 `main` 自动部署到 ECS
2. 支持手动指定 `ref` 发布

当前默认方案为 `self-hosted runner`（runner 运行在 ECS 本机），无需配置 ECS SSH Secrets。
你只需配置 Variable：`ECS_WORKDIR=/opt/videobling`，并按文档完成 runner 安装。
完整步骤见：`/Users/bytedance/Documents/VideoBling_local/DEPLOYMENT_CN.md` 第 13 节。

## 本机直接运行（非 Docker）

以下方式适合你要本机调试 Python/Node 代码时使用。

## 本机前置依赖

### 1) Python 3.9+

```bash
python3 --version
```

### 2) Node.js 20+

```bash
node -v
npm -v
```

### 3) ffmpeg / ffprobe

```bash
ffmpeg -version
ffprobe -version
```

## 启动步骤

### 1) 安装后端依赖

```bash
cd /Users/bytedance/Documents/VideoBling_local
./scripts/setup_backend.sh
```

### 2) 启动 API

```bash
cd /Users/bytedance/Documents/VideoBling_local
./scripts/start_api.sh
```

### 3) 启动 Worker

新终端执行：

```bash
cd /Users/bytedance/Documents/VideoBling_local
./scripts/start_worker.sh
```

### 4) 启动前端

新终端执行：

```bash
cd /Users/bytedance/Documents/VideoBling_local
./scripts/start_web.sh
```

打开页面：`http://localhost:5173`

## 配置说明

配置保存在：

- `/Users/bytedance/Documents/VideoBling_local/runtime/config.json`
- `/Users/bytedance/Documents/VideoBling_local/runtime/config_presets.json`

前端支持将“模型与 Prompt 控制台”保存为预设，并在页面内一键切换到指定预设（切换后会同步写入当前生效配置）。
前端 Pipeline 区域提供“启用 ASR 文本纠错”开关，关闭后将跳过纠错调用以降低耗时与成本。
队列详情弹窗支持“从任意阶段重跑”，会创建新任务并复用该阶段之前的中间产物。

按需求使用明文存储（本机复用）。

## 任务与产物

- 任务目录：`/Users/bytedance/Documents/VideoBling_local/runtime/jobs/{job_id}/`
- 队列 SQLite：`/Users/bytedance/Documents/VideoBling_local/runtime/queue.sqlite`
- 应用 SQLite：`/Users/bytedance/Documents/VideoBling_local/runtime/app.sqlite3`

## 测试

```bash
cd /Users/bytedance/Documents/VideoBling_local
source .venv/bin/activate
export PYTHONPATH=/Users/bytedance/Documents/VideoBling_local/backend
pytest -q
```

E2E 默认跳过。需要真实环境时：

```bash
RUN_E2E=1 pytest tests/e2e -q
```

## 注意事项

1. Seedance 提交/轮询字段在不同版本可能有差异，当前适配器做了多字段兜底解析。
2. 当前为单用户本机 MVP，不包含鉴权。
3. 如果 Seedance 返回无音轨，系统会自动补静音继续拼接。
4. ASR 适配器会先尝试极速版 `recognize/flash`，失败后自动回退到标准版 `submit/query`。如仍报 `requested grant not found` / `resourceId ... is not allowed` / `requested resource not granted`，请在前端 ASR 配置里确认 `Resource ID` 与火山语音控制台授予值一致（常见值：`volc.bigasr.auc_turbo`、`volc.bigasr.auc`、`volc.seedasr.auc`）。
5. LLM 的 `model` 需要填写方舟可访问的模型/端点 ID（例如 `doubao-seed-2-0-pro-260215`），不要只写简写名（如 `seed-2.0-pro`），否则会报 `InvalidEndpointOrModel.NotFound`。
6. Pipeline 支持 `enable_asr_polish` 开关。关闭后会跳过“ASR文本纠错”大模型调用，直接使用 ASR 原始转写进入脚本生成。
