"""Job directory layout, output discovery, display names and cleanup."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.config import Settings

CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".flv": "video/x-flv",
    ".ts": "video/mp2t",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".opus": "audio/ogg",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
}

_UNSAFE_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
_OUTPUT_PREFIX = "media."
_IGNORED_SUFFIXES = {".part", ".ytdl", ".tmp"}


def job_dir(settings: Settings, job_id: str) -> Path:
    return settings.jobs_dir / job_id


def prepare_job_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".tmp").mkdir(exist_ok=True)


def find_output(directory: Path) -> Path | None:
    """Return the largest finished media file, ignoring temp/partial artifacts."""
    if not directory.is_dir():
        return None
    candidates = [
        entry
        for entry in directory.glob(f"{_OUTPUT_PREFIX}*")
        if entry.is_file() and entry.suffix.lower() not in _IGNORED_SUFFIXES
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: entry.stat().st_size)


def content_type_for(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def display_filename(title: str | None, suffix: str) -> str:
    base = _UNSAFE_FILENAME.sub("_", (title or "").strip())
    base = re.sub(r"\s+", " ", base).strip(" .")
    if not base:
        base = "video"
    base = base[:120].rstrip(" .") or "video"
    extension = suffix if suffix.startswith(".") else f".{suffix}" if suffix else ""
    return f"{base}{extension.lower()}"


def remove_job_dir(directory: Path) -> None:
    shutil.rmtree(directory, ignore_errors=True)


def disk_free_bytes(directory: Path) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(directory).free


def cleanup_orphans(jobs_dir: Path, known_ids: set[str]) -> int:
    """Remove job directories that have no DB row. Returns the number removed."""
    if not jobs_dir.is_dir():
        return 0
    removed = 0
    for entry in jobs_dir.iterdir():
        if entry.is_dir() and entry.name not in known_ids:
            remove_job_dir(entry)
            removed += 1
    return removed
