# ---- build stage: resolve locked deps into /app/.venv -----------------------
FROM ghcr.io/astral-sh/uv:0.11.6 AS uv

FROM python:3.12-slim AS builder

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY app ./app

# Fail the build if the JS runtime / EJS support is missing.
RUN .venv/bin/deno --version \
    && .venv/bin/python -c "import importlib.metadata as m; print('yt-dlp-ejs', m.version('yt-dlp-ejs'))"

# ---- runtime stage ----------------------------------------------------------
FROM python:3.12-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/app \
       --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=root:root /app/.venv /app/.venv
COPY --chown=root:root app /app/app

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    YTP_DATA_DIR=/data \
    HOME=/home/app \
    DENO_DIR=/home/app/.cache/deno

RUN mkdir -p /data \
    && chown -R app:app /data /home/app \
    && deno --version \
    && ffmpeg -version | head -1 \
    && python -c "import importlib.metadata as m; print('yt-dlp-ejs', m.version('yt-dlp-ejs'))" \
    && python -c "import yt_dlp; print('yt-dlp', yt_dlp.version.__version__)"

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
