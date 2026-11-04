"""Downloader interface shared by the real yt-dlp implementation and test fakes."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from yt_dlp.utils import DownloadCancelled


class JobCancelled(DownloadCancelled):
    """Raised from yt-dlp hooks to abort a job. Subclassing DownloadCancelled lets
    yt-dlp unwind cleanly instead of printing a traceback."""

    def __init__(self, reason: str = "canceled") -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass
class VideoInfo:
    url: str
    platform: str
    video_id: str
    title: str
    uploader: str | None
    duration_seconds: int | None
    thumbnail_url: str | None
    webpage_url: str
    qualities: list[dict] = field(default_factory=list)


@dataclass
class ProgressUpdate:
    percent: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed_bps: float | None = None
    eta_seconds: int | None = None
    stage: str | None = None
    phase: str | None = None

    def as_dict(self) -> dict:
        return {
            "percent": self.percent,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "speed_bps": self.speed_bps,
            "eta_seconds": self.eta_seconds,
            "stage": self.stage,
        }


@dataclass
class DownloadRequest:
    job_id: str
    url: str
    quality: str
    job_dir: Path
    cancel_event: threading.Event
    on_progress: Callable[[ProgressUpdate], None]
    on_metadata: Callable[[str | None, str | None], None]


@dataclass
class DownloadResult:
    path: Path
    title: str | None
    thumbnail_url: str | None


class Downloader(Protocol):
    def probe(self, url: str) -> VideoInfo: ...

    def cached_info(self, url: str) -> VideoInfo | None: ...

    def download(self, request: DownloadRequest) -> DownloadResult: ...
