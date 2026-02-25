# VideoBling 公网部署指南（非 Tailscale，火山引擎 ECS）

本指南目标是让你在 1-2 天内完成可对外访问部署，并拿到一个可分享给客户的固定地址：

- `http://<EIP>`

## 1. 你会得到什么

1. 客户访问统一网址（公网 EIP），输入 Basic Auth 账号密码后可使用系统。
2. 你每次更新代码后执行发布脚本，客户仍访问同一 URL。
3. 服务运行在 ECS 单机 Docker Compose：`gateway + backend + worker`。

## 2. 架构说明

1. `gateway`（Nginx）：
   - 托管前端构建产物
   - 反代 `/api` 到 `backend`
   - 启用 Basic Auth
2. `backend`（FastAPI）：
   - 仅容器内暴露 `8000`
3. `worker`（Huey）：
   - 消费任务队列
4. 数据目录：
   - 宿主机 `RUNTIME_DIR` 映射到容器 `/app/runtime`

## 3. 前置准备（控制台）

### 3.1 创建 ECS

1. 建议规格：4C8G（首版小规模足够）。
2. 系统：Ubuntu 22.04 LTS（推荐）。
3. 绑定 EIP。

### 3.2 安全组配置

只放行：

1. `80/tcp`：`0.0.0.0/0`
2. `22/tcp`：仅你的办公公网 IP

明确不要放行：

1. `5173`
2. `18000`
3. `8000`

## 4. 服务器初始化（第一次）

SSH 登录 ECS 后执行：

```bash
mkdir -p /opt
cd /opt
git clone <your-repo-url> videobling
cd videobling
```

运行初始化脚本（安装 Docker 与 Compose）：

```bash
sudo ./scripts/init_ecs_ubuntu.sh
```

如果提示当前用户加入 docker 组，重新登录一次 SSH。

## 5. 准备生产配置

```bash
cd /opt/videobling
cp .env.prod.example .env.prod
```

编辑 `.env.prod`：

```dotenv
RUNTIME_DIR=/data/videobling/runtime
BASIC_AUTH_FILE=/data/videobling/secrets/.htpasswd
GATEWAY_PORT=80
DEPLOY_BRANCH=main
PUBLIC_EIP=<你的EIP，如 1.2.3.4>
```

创建持久化目录与认证文件：

```bash
mkdir -p /data/videobling/runtime/jobs
mkdir -p /data/videobling/secrets

# 生成 Basic Auth 用户（示例用户 videobling）
docker run --rm httpd:2.4-alpine htpasswd -nbB videobling 'YourStrongPassword' > /data/videobling/secrets/.htpasswd
chmod 600 /data/videobling/secrets/.htpasswd
```

## 6. 首次部署

```bash
cd /opt/videobling
./scripts/deploy_prod.sh
```

脚本会自动：

1. 启动并构建生产容器
2. 打印容器状态
3. 输出可分享公网链接（优先 `PUBLIC_EIP`，否则尝试自动探测）

## 7. 如何拿到并确认“客户可访问链接”

### 7.1 直接生成链接

```bash
cd /opt/videobling
./scripts/print_access_url.sh
```

输出类似：

```text
Public URL: http://1.2.3.4
```

### 7.2 服务器本机验证

```bash
curl -I http://127.0.0.1
```

预期返回 `401 Unauthorized`（说明 Basic Auth 在生效，网关已启动）。

### 7.3 外网验证

在你本地电脑（或手机 4G）执行：

```bash
curl -I http://<EIP>
```

预期返回 `401 Unauthorized`，再用浏览器访问该 URL 并输入账号密码，看到 VideoBling 页面。

## 8. 发布更新（网址不变）

```bash
cd /opt/videobling
./scripts/update_prod.sh main
```

或不传参数（默认 `.env.prod` 里的 `DEPLOY_BRANCH`）。

更新后脚本会再次打印公网访问 URL，客户继续用同一链接。

## 9. 回滚

按 git tag 或 commit 回滚：

```bash
cd /opt/videobling
./scripts/rollback_prod.sh <git-tag-or-commit>
```

## 10. 运维检查命令

```bash
cd /opt/videobling
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
docker compose -f docker-compose.prod.yml --env-file .env.prod logs --tail=200 backend worker gateway
```

## 11. 常见问题

1. 浏览器打不开 URL
   - 先查 ECS 安全组是否放行 `80/tcp`
   - 再查 EIP 是否绑定当前 ECS
2. 返回 502
   - 检查 `backend` 是否健康：`docker compose ... ps`
3. 任务日志不刷新
   - 检查网关是否使用仓库内 `deploy/gateway/nginx.conf`（SSE 已配置禁用缓冲）
4. URL 打开但没有弹认证框
   - 检查 `BASIC_AUTH_FILE` 路径是否正确挂载

## 12. 默认策略

1. 入口协议：HTTP（首版过渡可用）
2. 认证方式：Basic Auth（共享账号）
3. 数据保留：最近 20 个任务（通过现有 cleanup API）
4. 后续升级：域名 + 备案 + HTTPS + 更细粒度鉴权

## 13. GitHub Actions 自动部署到 ECS

仓库已提供工作流：

- `/Users/bytedance/Documents/VideoBling_local/.github/workflows/deploy-ecs.yml`

触发方式：

1. 推送到 `main` 自动部署
2. Actions 页面手动触发 `workflow_dispatch`，可指定 `ref`

### 13.1 ECS 端一次性准备（让服务器可 `git pull`）

在 ECS 上执行：

```bash
cd /opt/videobling
git remote -v
```

如果仓库是私有仓库，推荐使用 Deploy Key：

```bash
ssh-keygen -t ed25519 -C "videobling-ecs-deploy" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

把公钥添加到 GitHub 仓库：

1. Repo -> `Settings` -> `Deploy keys` -> `Add deploy key`
2. 勾选 `Allow read access`

然后切换 ECS 仓库 remote 为 SSH：

```bash
cd /opt/videobling
git remote set-url origin git@github.com:Messatsu-0/VideoBling_Volc.git
ssh -T git@github.com
```

### 13.2 GitHub 仓库配置

在 GitHub 仓库中设置以下 Secrets（`Settings -> Secrets and variables -> Actions`）：

1. `ECS_HOST`：ECS 公网 IP
2. `ECS_USER`：SSH 用户（如 `root` 或普通运维用户）
3. `ECS_SSH_KEY`：用于登录 ECS 的私钥全文（多行原样粘贴）
4. `ECS_PORT`：可选，默认 `22`

设置以下 Variables（可选）：

1. `ECS_WORKDIR`：服务器项目目录，默认 `/opt/videobling`

### 13.3 首次验证

1. 在 GitHub 打开 `Actions`，运行 `Deploy to ECS`（手动触发一次）。
2. 确认日志中 `./scripts/update_prod.sh` 成功执行。
3. ECS 上执行：

```bash
cd /opt/videobling
./scripts/print_access_url.sh
```

输出 `Public URL: http://<EIP>` 后，即可把该链接发给客户。

### 13.4 后续更新方式

1. 本地提交并推送到 `main`：

```bash
git push origin main
```

2. GitHub Actions 自动 SSH 到 ECS 并执行更新。
3. 客户继续访问同一个 URL（`http://<EIP>`）。
