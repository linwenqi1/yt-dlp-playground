# yt-dlp Playground

粘贴 YouTube / Bilibili 链接 → 查看视频信息与可用清晰度 → 异步下载并显示进度 → 在浏览器保存文件。

本地优先设计，随时可以搬上 VPS + Cloudflare Pages：后端容器化，前端静态部署，`/api/*` 由 Pages Function 反向代理到 Cloudflare Tunnel，外层用 Cloudflare Access 保护。

## 功能

- 支持平台：YouTube、Bilibili（精确域名白名单，不做通用代理）。
- 清晰度：`best`、`2160p/1440p/1080p/720p/480p/360p`（仅列出源实际提供的高度）、`audio`（MP3 192kbps）。
- 异步任务：排队、进度、速度/ETA、取消、失败原因（中文）、TTL 自动清理。
- 下载：音视频合并（FFmpeg）、真实扩展名与 MIME、HTTP Range（206）断点续传、浏览器保存。
- 单实例共享密钥 `X-API-Token`，供 Pages Function 注入；`/health` 免鉴权。

## 快速开始（本地开发）

依赖：Python 3.12 + [uv](https://docs.astral.sh/uv/)、Node 24 + pnpm 10、FFmpeg 6+。Deno 由 `yt-dlp[deno]` 安装进虚拟环境，无需单独安装。

```bash
make setup          # uv sync + pnpm install

# 终端 A
make dev-backend    # http://127.0.0.1:8000  (文档 /api/docs)

# 终端 B
make dev-frontend   # http://localhost:5173
```

打开 `http://localhost:5173`，粘贴链接即可。Vite 把 `/api` 代理到 `127.0.0.1:8000`。

常用命令：

```bash
make test      # 后端离线测试（网络测试默认跳过）
make lint      # ruff check + format --check + tsc -b
make build     # 前端生产构建
make check     # lint + test + build
```

可选配置：复制 `backend/.env.example` 为 `backend/.env`（变量均以 `YTP_` 前缀，见下表）。

| 变量 | 默认 | 说明 |
|---|---|---|
| `YTP_DATA_DIR` | `./data` | SQLite 与下载产物 |
| `YTP_MAX_CONCURRENT_JOBS` | `1` | 并行下载数 |
| `YTP_MAX_QUEUED_JOBS` | `20` | 队列上限，超出 503 |
| `YTP_JOB_TTL_HOURS` | `24` | 任务与文件保留时长 |
| `YTP_MAX_FILESIZE_MB` | `2048` | 单文件上限 |
| `YTP_MAX_JOB_MINUTES` | `120` | 单任务硬超时 |
| `YTP_INFO_CACHE_TTL_SECONDS` | `600` | 解析结果缓存 |
| `YTP_INFO_CONCURRENCY` | `2` | 同时解析数 |
| `YTP_COOKIES_FILE` | 空 | 可选 cookies.txt（登录态/风控） |
| `YTP_PROXY` | 空 | 可选 HTTP 代理 |
| `YTP_IMPERSONATE` | 空 | 可选 TLS 指纹，如 `chrome` |
| `YTP_API_TOKEN` | 空 | 非空时 `/info`、`/jobs/*` 要求 `X-API-Token` |

## 架构

```
Browser → Vite/Pages
            ├─ 静态页面（Vite + React + TS）
            └─ /api/* → FastAPI (127.0.0.1:8000)
                          ├─ api/        协议层：校验、错误信封
                          ├─ manager     进程内队列、worker、取消、清理
                          ├─ downloader  yt-dlp + Deno/EJS + FFmpeg；解析缓存
                          └─ storage     SQLite（WAL）+ data/jobs/<id>/media.<ext>
```

- 后端**必须单进程**（进程内队列）；不要加 `--workers`。
- SQLite 每次操作新建连接，所有 SQL 集中在 `storage/jobs_repo.py`。
- API 契约固定在 `/api/v1`，错误码稳定；前端类型见 `frontend/src/api/types.ts`。
- `yt-dlp` 是唯一的外部下载依赖，集中在 `downloader/ytdlp.py`。

## Docker

```bash
docker build -t ytp-backend:dev backend        # 或 make docker-build
cp deploy/compose.env.example deploy/compose.env
docker compose -f deploy/docker-compose.yml up -d backend
curl -fsS http://127.0.0.1:8000/api/v1/health
```

容器以非 root 用户运行，数据在命名卷 `ytp-data`，端口只绑 `127.0.0.1`。镜像内已断言 `deno`、`ffmpeg`、`yt-dlp-ejs` 存在。

部署到 VPS / Tunnel / Access / Pages 的完整步骤见 [deploy/README.md](deploy/README.md)。

## 已知限制

- 仅单个视频：不支持播放列表、多 P、直播、字幕、任意 format 选择。
- 不支持 `b23.tv` 短链，请粘贴展开后的 `bilibili.com` 链接。
- YouTube 机房 IP 可能触发 bot 校验；Bilibili 高码率通常需要 cookies。
- 任务不跨重启恢复：运行中的任务在重启后标记为 `interrupted`。
- SQLite + 进程内队列 = 单实例；不做多用户、鉴权体系或分布式队列。
- 大文件经 Pages Function 流式转发会占用 VPS 出口带宽；慢解析仍可能遇到 Cloudflare 首字节超时（524）。
- 不提供 CORS：浏览器只能走同源代理，直连 API 仅适合 curl。

## 升级 yt-dlp

平台站点经常变化，yt-dlp 需要保持较新：

```bash
cd backend
uv lock --upgrade-package yt-dlp
uv sync
make test
# 跑一次真实 /info 与下载 smoke，再提交 uv.lock 并重建镜像
```
