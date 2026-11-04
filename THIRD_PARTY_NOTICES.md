# 来源与第三方许可说明

本文件说明本项目的来源、源代码许可，以及运行时随附的第三方组件及其许可。所有版本以仓库中的 `backend/uv.lock`、`frontend/pnpm-lock.yaml` 和 `backend/Dockerfile` 为准。

## 1. 项目来源

本项目（yt-dlp Playground）是独立编写的 Playground，**不是 yt-dlp 的 fork，也未获得 yt-dlp、YouTube/Google 或哔哩哔哩的隶属、赞助或背书**。

核心下载与解析能力来自上游开源项目：

| 上游项目 | 作用 | 上游地址 | 许可 |
|---|---|---|---|
| yt-dlp | 视频信息解析与下载引擎 | https://github.com/yt-dlp/yt-dlp | Unlicense |
| yt-dlp-ejs | yt-dlp 的 EJS 挑战脚本支持 | https://github.com/yt-dlp/ejs | Unlicense AND MIT AND ISC |
| Deno | yt-dlp 所需的 JavaScript runtime | https://github.com/denoland/deno | MIT |
| FFmpeg | 音视频合并、转码（MP3） | https://ffmpeg.org | GPL-2.0-or-later（Debian 构建） |
| curl-cffi | TLS 指纹模拟（可选） | https://github.com/lexiforest/curl_cffi | MIT |

前端与部署侧：

| 上游项目 | 作用 | 上游地址 | 许可 |
|---|---|---|---|
| React / React DOM | 前端 UI | https://github.com/facebook/react | MIT |
| Vite | 前端开发与构建 | https://github.com/vitejs/vite | MIT |
| Cloudflare Pages Functions | `/api/*` 反向代理与 Access 校验 | https://developers.cloudflare.com/pages/ | 平台服务条款 |
| @cloudflare/pages-plugin-cloudflare-access | Access JWT 校验中间件 | https://github.com/cloudflare/pages-plugins | MIT |
| Cloudflare Tunnel / cloudflared | 公网到 VPS 的隧道（可选） | https://github.com/cloudflare/cloudflared | Apache-2.0 |

本项目与 YouTube（Google LLC）、哔哩哔哩（上海幻电信息科技有限公司）无关联；相关名称与商标归其各自权利人所有。

## 2. 本项目许可

除第三方组件外，本仓库的源代码采用 **MIT License**，全文见 [LICENSE](LICENSE)。

MIT 仅适用于本仓库自行编写的代码，**不改变**任何第三方组件自身的许可条款。

## 3. 后端运行时组件（Python）

以下组件会随 Docker 镜像分发（`uv sync --no-dev`）。版本取自当前锁文件，升级依赖后应以 `uv tree --no-dev` 与各包元数据为准。

| 包 | 版本 | 许可 |
|---|---|---|
| fastapi | 0.162.0 | MIT |
| starlette | 1.10.0 | BSD-3-Clause |
| pydantic / pydantic-core | 2.14.2 / 2.50.2 | MIT |
| pydantic-settings | 2.16.2 | MIT |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| typing-extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |
| anyio | 4.16.0 | MIT |
| opentelemetry-api | 1.45.2 | Apache-2.0 |
| uvicorn | 0.54.0 | BSD-3-Clause |
| click | 8.5.0 | BSD-3-Clause |
| h11 | 0.16.0 | MIT |
| httptools | 0.9.0 | MIT |
| uvloop | 0.23.0 | MIT |
| watchfiles | 1.3.0 | MIT |
| websockets | 17.4 | BSD-3-Clause |
| PyYAML | 6.0.3 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| yt-dlp | 2026.10.26 | Unlicense |
| yt-dlp-ejs | 0.8.0 | Unlicense AND MIT AND ISC |
| deno | 2.9.8 | MIT |
| curl-cffi | 0.17.0 | MIT |
| cffi | 2.1.1 | MIT-0 |
| pycparser | 3.12 | BSD-3-Clause |
| certifi | 2026.10.23 | MPL-2.0 |
| brotli | 1.2.1 | MIT |
| mutagen | 1.48.1 | **GPL-2.0-or-later** |
| pycryptodomex | 3.24.1 | BSD-2-Clause 与 Public Domain |
| requests | 2.34.2 | Apache-2.0 |
| charset-normalizer | 3.5.2 | MIT |
| idna | 3.20 | BSD-3-Clause |
| urllib3 | 2.8.0 | MIT |

仅开发环境使用、**不进入运行时镜像**的依赖：`pytest`（MIT）、`httpx`/`httpcore`（BSD-3-Clause）、`ruff`（MIT）、`iniconfig`（MIT）、`pluggy`（MIT）、`Pygments`（BSD-2-Clause）、`packaging`（Apache-2.0 OR BSD-2-Clause）。

## 4. 前端与构建组件（Node）

| 包 | 版本 | 许可 | 是否进入产物 |
|---|---|---|---|
| react | 19.3.1 | MIT | 是（静态页面） |
| react-dom | 19.3.1 | MIT | 是（静态页面） |
| @cloudflare/pages-plugin-cloudflare-access | 1.0.5 | MIT | 是（Pages Functions 构建） |
| vite | 7.3.7 | MIT | 否（构建工具） |
| typescript | 5.9.3 | Apache-2.0 | 否（构建工具） |
| wrangler | 4.157.0 | MIT OR Apache-2.0 | 否（本地/部署工具） |
| @vitejs/plugin-react | 5.2.0 | MIT | 否（构建工具） |
| @cloudflare/workers-types | 4.20260702.1 | MIT OR Apache-2.0 | 否（类型定义） |
| @types/react / @types/react-dom | 19.3.0 | MIT | 否（类型定义） |

前端传递依赖（如 React 的 `scheduler`）同样为 MIT，完整列表可通过 `pnpm licenses list` 在 `frontend/` 下查看。

## 5. 容器基础镜像与系统组件

Docker 镜像基于 `python:3.12-slim`（Debian）：Python 采用 PSF-2.0 许可；Debian 基础系统包含 GPL/LGPL 组件（如 bash、coreutils、glibc、OpenSSL 等），各自遵循其发行版许可。镜像还通过 apt 安装：

| 组件 | 许可 | 说明 |
|---|---|---|
| ffmpeg 7.1.5（Debian trixie） | **GPL-2.0-or-later** | Debian 默认构建启用 `--enable-gpl`，二进制整体按 GPL-2.0-or-later 分发 |
| FFmpeg 依赖的编解码库（libx264、libx265、libavcodec 等） | GPL/LGPL 等 | 详见镜像内 `/usr/share/doc/*/copyright` |
| ca-certificates | MPL-2.0 等 | Mozilla CA 证书及其分发条款 |

## 6. GPL 与镜像分发（重要）

后端镜像同时包含 **GPL-2.0-or-later** 组件（Debian ffmpeg 二进制、Python 包 `mutagen`）以及 Debian 基础系统中的 GPL/LGPL 组件。因此：

- **仅在本机或私有服务器自用、不对外分发镜像**时，通常不触发 GPL 的“分发”义务。
- **若公开分发镜像**（推送到公共 registry、提供给第三方等），需要同时遵守 GPL-2.0-or-later：向接收者提供相应组件的完整对应源码，并附带许可全文与修改说明；仅以 MIT 许可分发本项目代码并不能免除这些义务。
- 对应源码可从 Debian（`apt-get source ffmpeg`）与 PyPI（`mutagen` 源码包）获取；构建参数见 `backend/Dockerfile`。
- 本文件不是法律意见；如有商业分发需求，请自行评估或咨询专业意见。

## 7. 使用限制与免责声明

- 本项目仅用于个人学习、研究与自建工具，**不得作为公开的下载代理服务运营**。
- 下载内容可能受著作权与平台服务条款约束；使用者须自行确认拥有相应权利，并遵守 YouTube、哔哩哔哩所在地法律及其服务条款。
- 本项目不绕过付费、DRM 或访问控制，也不提供任何内容；仅封装 yt-dlp 的公开能力。
- 软件按 MIT 许可“按原样”提供，不附带任何明示或默示担保。

## 8. 如何核对

```bash
# 后端运行时依赖及版本
cd backend && uv tree --no-dev

# 后端已安装包的许可元数据
cd backend && uv run python -c "import importlib.metadata as m; [print(d.metadata['Name'], d.version, d.metadata.get('License-Expression') or d.metadata.get('License')) for d in m.distributions()]"

# 前端依赖许可（需先 pnpm install）
cd frontend && pnpm licenses list

# 镜像内系统包许可
docker run --rm ytp-backend:dev sh -c 'cat /usr/share/doc/ffmpeg/copyright | head -40'
```
