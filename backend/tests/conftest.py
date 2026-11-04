from __future__ import annotations

import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.downloader.base import (
    DownloadRequest,
    DownloadResult,
    JobCancelled,
    ProgressUpdate,
    VideoInfo,
)
from app.main import create_app


def make_settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "data_dir": tmp_path / "data",
        "max_concurrent_jobs": 1,
        "max_queued_jobs": 1,
        "job_ttl_hours": 24,
        "max_filesize_mb": 64,
        "max_job_minutes": 120,
        "info_cache_ttl_seconds": 0,
        "info_concurrency": 1,
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def make_info(url: str, platform: str = "bilibili") -> VideoInfo:
    return VideoInfo(
        url=url,
        platform=platform,
        video_id="BV1xx411c7mD",
        title="示例视频",
        uploader="示例UP主",
        duration_seconds=123,
        thumbnail_url="https://example.com/cover.jpg",
        webpage_url=url,
        qualities=[
            {"id": "best", "kind": "video", "height": None},
            {"id": "720p", "kind": "video", "height": 720},
            {"id": "audio", "kind": "audio", "height": None},
        ],
    )


class FakeDownloader:
    """Deterministic stand-in for YtDlpDownloader."""

    def __init__(self) -> None:
        self.probe_result: VideoInfo | None = None
        self.probe_error: Exception | None = None
        self.download_error: Exception | None = None
        self.block_until_released = False
        self.release = threading.Event()
        self.entered = threading.Event()
        self.payload = b"0123456789" * 20
        self.downloads: list[DownloadRequest] = []
        self.cached: dict[str, VideoInfo] = {}

    def cached_info(self, url: str) -> VideoInfo | None:
        return self.cached.get(url)

    def probe(self, url: str) -> VideoInfo:
        if self.probe_error is not None:
            raise self.probe_error
        return self.probe_result or make_info(url)

    def download(self, request: DownloadRequest) -> DownloadResult:
        self.downloads.append(request)
        request.on_metadata("示例标题", "https://example.com/cover.jpg")
        request.on_progress(
            ProgressUpdate(
                percent=50.0,
                downloaded_bytes=100,
                total_bytes=200,
                speed_bps=1024.0,
                eta_seconds=1,
                stage="video",
                phase="downloading",
            )
        )
        self.entered.set()
        if self.download_error is not None:
            raise self.download_error
        if self.block_until_released:
            while not self.release.wait(0.02):
                if request.cancel_event.is_set():
                    raise JobCancelled("canceled")
        if request.cancel_event.is_set():
            raise JobCancelled("canceled")
        path = request.job_dir / "media.mp4"
        path.write_bytes(self.payload)
        return DownloadResult(path=path, title="示例标题", thumbnail_url=None)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def fake_downloader() -> FakeDownloader:
    return FakeDownloader()


@pytest.fixture
def client(settings: Settings, fake_downloader: FakeDownloader):
    app = create_app(settings, fake_downloader)
    with TestClient(app) as test_client:
        yield test_client
