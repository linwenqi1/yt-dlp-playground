# 部署指南（VPS + Cloudflare Tunnel + Access + Pages）

本目录只负责**后端容器**与**Cloudflare 侧接线**。前端构建与 Pages Functions 在 `frontend/`。

目标拓扑：

```
Browser
  │
  ▼
Cloudflare Access（仅自定义域名生效）
  │
  ▼
Cloudflare Pages（静态资源 + /api/* Pages Function）
  │  X-API-Token（服务端注入，浏览器不可见）
  ▼
Cloudflare Tunnel（cloudflared 容器）
  │
  ▼
VPS:127.0.0.1:8000 → backend 容器
  └─ /data 命名卷：SQLite + 下载产物
```

## 0. 前置条件

- VPS：Linux x86_64 或 arm64、Docker Engine + Compose v2、至少 2 GB 内存（FFmpeg 合并需要）、磁盘按 `YTP_JOB_TTL_HOURS` 与文件大小预留。
- 镜像**在 VPS 上构建**（Deno wheel 与架构相关，不要跨架构拷贝镜像）。
- 一个托管在 Cloudflare 的域名；`cloudflared` 使用 Tunnel token 运行，无需开放入站端口。
- 后端只能单进程运行（进程内队列）；不要给 uvicorn 加 `--workers`，也不要横向扩容多个副本共享同一个 `/data`。

## 1. 启动后端

```bash
# 在 VPS 上
git clone <repo> && cd yt-dlp-playground

cp deploy/compose.env.example deploy/compose.env
$EDITOR deploy/compose.env          # 至少设置 YTP_API_TOKEN

docker compose -f deploy/docker-compose.yml build
docker compose -f deploy/docker-compose.yml up -d backend
docker compose -f deploy/docker-compose.yml ps        # 等待 backend 变 healthy
curl -fsS http://127.0.0.1:8000/api/v1/health
```

- `ports` 只绑 `127.0.0.1:8000`：公网只能经 Tunnel 访问。若完全不需要本机 curl，可删掉该映射，让 cloudflared 走容器网络 `http://backend:8000`。
- 数据在命名卷 `yt-dlp-playground_ytp-data`（项目名来自 compose 的 `name:`）。不要改成 WSL2/Docker Desktop 的 bind mount：9p/drvfs 下 SQLite 文件锁不可靠。
- 更新：`git pull` → `docker compose -f deploy/docker-compose.yml build` → `up -d backend`。`/data` 与任务记录保留。
- 重置：`docker compose -f deploy/docker-compose.yml down -v`（**会删除所有下载产物与数据库**）。

可选：把 cookies 放进卷，供登录态/风控使用。

```bash
docker compose -f deploy/docker-compose.yml cp ./cookies.txt backend:/data/cookies.txt
# 然后在 compose.env 设置 YTP_COOKIES_FILE=/data/cookies.txt 并重启 backend
```

## 2. Cloudflare Tunnel

1. Zero Trust 控制台 → Networks → Tunnels → Create a tunnel（Cloudflared）。
2. 复制 tunnel token，填入 `deploy/compose.env`：`TUNNEL_TOKEN=...`。
3. 添加 Public Hostname：`api.example.com` → Service `HTTP` → `backend:8000`（cloudflared 与 backend 在同一 compose 网络）。
4. 启动隧道：

```bash
docker compose -f deploy/docker-compose.yml --profile tunnel up -d
docker compose -f deploy/docker-compose.yml logs -f cloudflared
curl -fsS https://api.example.com/api/v1/health
```

5. **不要**给 `api.example.com` 单独套 Access 策略：Pages Function 需要直连它；如果确有需要，改用 Access Service Token，并让 Function 携带 `CF-Access-Client-Id` / `CF-Access-Client-Secret`（本项目默认不带）。

此时直连 API 应当：

- 未设置 `YTP_API_TOKEN`：任何人可访问 —— 仅限首次联调，联调完立刻设置。
- 已设置：`curl https://api.example.com/api/v1/jobs` 返回 401；带 `-H "X-API-Token: ..."` 才成功。

## 3. Cloudflare Access

1. Zero Trust → Access → Applications → Add an application → Self-hosted。
2. 域名填 Pages 的**自定义域名**（例如 `ytp.example.com`），**不要**用 `*.pages.dev`：Pages 的 `pages.dev` 别名无法被 Access 覆盖。
3. 添加策略（邮箱验证码 / Google / GitHub 等），保存。
4. 记下 Application Audience (AUD) Tag 与团队域名 `https://<team>.cloudflareaccess.com`，稍后填进 Pages 变量 `ACCESS_AUD`、`ACCESS_DOMAIN`。

> 安全边界：`pages.dev` 别名仍可绕过 Access 直接访问静态页面，但 `/api/*` 由 Pages Function 校验 Access JWT（`Cf-Access-Jwt-Assertion`），未通过返回 401；后端再校验共享 token。两层都启用才完整。

## 4. Cloudflare Pages（前端 + Functions）

1. Pages → Create project → 连接 Git 仓库。
2. 构建配置：
   - Root directory：`frontend`
   - Build command：`pnpm build`
   - Build output：`dist`
   - 环境变量：`NODE_VERSION=24`（或 `PNPM_VERSION=10`，按平台可用版本填写）
3. 变量（Settings → Environment variables，Production）：

| 变量 | 说明 |
|---|---|
| `ENVIRONMENT` | `production`（只有 `development` 才跳过 Access 校验，切勿在生产设置） |
| `API_ORIGIN` | `https://api.example.com`（仅 scheme+host，无路径、无尾斜杠） |
| `ACCESS_DOMAIN` | `https://<team>.cloudflareaccess.com` |
| `ACCESS_AUD` | Access 应用的 AUD Tag |
| `API_TOKEN` | **Secret**，与后端 `YTP_API_TOKEN` 完全一致 |

```bash
cd frontend
pnpm dlx wrangler pages secret put API_TOKEN --project-name yt-dlp-playground
```

4. 在 Pages → Custom domains 绑定 `ytp.example.com`，并为该域名配置 Access（第 3 步）。
5. 部署后验证：

```bash
curl -i https://ytp.example.com/api/v1/health      # 未登录 Access 时应被拦
# 浏览器登录 Access 后：解析 → 下载 → 保存；另检查 Range：
curl -r 0-99 -o /dev/null -w '%{http_code}\n' https://ytp.example.com/api/v1/jobs/<id>/file   # 206
```

## 5. 本地验证 Cloudflare 侧（不部署）

```bash
cd frontend
cp .dev.vars.example .dev.vars
# ENVIRONMENT=development, API_ORIGIN=http://127.0.0.1:8000, API_TOKEN 与后端一致或留空
pnpm dev:pages
# 另开终端：curl 8788 端口的 /api/v1/health、POST /info、文件 Range
```

`ENVIRONMENT=development` 会跳过 Access JWT 校验，仅用于本地；缺失配置时 middleware 一律 fail closed 返回 500/401。

## 6. 运维要点

- **健康检查**：镜像内建 HEALTHCHECK，每 30s 请求 `/api/v1/health`；compose 的 cloudflared 依赖 `service_healthy`。
- **清理**：终态任务在 `expires_at` 后由后台 sweeper 删除（默认 24h）。磁盘紧张时调小 `YTP_JOB_TTL_HOURS`。
- **日志**：`docker compose logs -f backend`；容器日志已限制为 10m × 3。
- **备份**：`/data` 含 SQLite 与视频，按需快照；视频是可再生的，通常只需保留配置。
- **代理/风控**：YouTube 机房 IP 常见 “Sign in to confirm”，Bilibili 高码率常见 412/需要 cookies。在 `compose.env` 配 `YTP_COOKIES_FILE` / `YTP_PROXY` 后重启。
- **升级 yt-dlp**：在开发机 `cd backend && uv lock --upgrade-package yt-dlp` → 提交 `uv.lock` → VPS 上重新 `build`。重建后跑一次 `/info` + 下载 smoke。
- **架构**：若 VPS 是 arm64，在 VPS 上构建；`yt-dlp[deno]` 若该架构缺 wheel，构建会在 `deno --version` 断言处失败，此时按 yt-dlp 文档安装官方 Deno 二进制并放入 `PATH`（`js_runtimes` 按名字查找）。
- **单实例**：进程内队列 + 单 SQLite 文件；多副本会导致任务丢失与写冲突。

## 7. 故障排查

| 现象 | 排查 |
|---|---|
| `wrangler pages dev` 返回 500 | `.dev.vars` 缺 `API_ORIGIN`/`ACCESS_DOMAIN`/`ACCESS_AUD`；middleware fail closed |
| Function 返回 401 | 生产环境未通过 Access（无 `Cf-Access-Jwt-Assertion`）；或 AUD/团队域名不匹配 |
| Function 返回 502 | `API_ORIGIN` 错误、Tunnel 未起、backend 不健康 |
| 后端直连 401 | 已设置 `YTP_API_TOKEN`，但请求未带 `X-API-Token`（或 Function secret 不一致） |
| 下载失败 `login_required` | 配置 cookies；机房 IP 触发风控 |
| `merge_failed` | 容器内缺 ffmpeg；检查 `docker compose exec backend ffmpeg -version` |
| 任务在重启后变 `interrupted` | 预期行为：任务不跨重启恢复 |
