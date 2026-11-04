from __future__ import annotations

import importlib.metadata
import shutil
from pathlib import Path

from fastapi import APIRouter, Request

from app import __version__

router = APIRouter()


def _ytdlp_version() -> str:
    try:
        return importlib.metadata.version("yt-dlp")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _detect_js_runtime() -> str | None:
    for runtime in ("deno", "node"):
        if shutil.which(runtime):
            return runtime
    return None


def _disk_free(data_dir: Path) -> int:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(data_dir).free
    except OSError:
        return 0


@router.get("/health")
def health(request: Request) -> dict:
    settings = request.app.state.settings
    manager = request.app.state.manager
    return {
        "status": "ok",
        "version": __version__,
        "yt_dlp_version": _ytdlp_version(),
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "js_runtime": _detect_js_runtime(),
        "queue_depth": manager.queue_depth,
        "active_jobs": manager.active_count,
        "disk_free_bytes": _disk_free(settings.data_dir),
    }
