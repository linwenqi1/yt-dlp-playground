from __future__ import annotations

import threading
from pathlib import Path

import pytest

from app.core import timeutil
from app.downloader.base import DownloadRequest, JobCancelled
from app.downloader.manager import JobManager
from app.downloader.ytdlp import _DownloadHooks
from app.errors import ApiError
from app.storage import jobs_repo
from app.storage.db import init_db
from tests.conftest import make_settings

PROGRESS = {
    "percent": None,
    "downloaded_bytes": None,
    "total_bytes": None,
    "speed_bps": None,
    "eta_seconds": None,
    "stage": None,
}


def create_row(settings, job_id: str, expires_at: str = "2099-01-01T00:00:00Z") -> None:
    jobs_repo.create_job(
        settings.db_path,
        job_id=job_id,
        url="https://www.bilibili.com/video/BV1",
        platform="bilibili",
        quality="720p",
        title=None,
        thumbnail_url=None,
        progress=PROGRESS,
        created_at=timeutil.iso(),
        expires_at=expires_at,
    )


def test_startup_recovers_interrupted_jobs(tmp_path: Path, fake_downloader) -> None:
    settings = make_settings(tmp_path)
    init_db(settings.db_path)
    create_row(settings, "running_job")
    jobs_repo.mark_running(settings.db_path, "running_job", timeutil.iso())
    (settings.jobs_dir / "running_job").mkdir(parents=True)
    (settings.jobs_dir / "orphan").mkdir()

    manager = JobManager(settings, fake_downloader)
    manager.start()
    try:
        row = jobs_repo.get_job(settings.db_path, "running_job")
        assert row["status"] == "failed"
        assert "interrupted" in row["error_json"]
        assert not (settings.jobs_dir / "running_job").exists()
        assert not (settings.jobs_dir / "orphan").exists()
    finally:
        manager.stop()


def test_sweep_removes_expired_jobs_and_files(tmp_path: Path, fake_downloader) -> None:
    settings = make_settings(tmp_path)
    init_db(settings.db_path)
    create_row(settings, "expired", expires_at="2000-01-01T00:00:00Z")
    jobs_repo.mark_running(settings.db_path, "expired", timeutil.iso())
    jobs_repo.complete_job(
        settings.db_path,
        "expired",
        filename="a.mp4",
        size_bytes=1,
        content_type="video/mp4",
        finished_at=timeutil.iso(),
        expires_at="2000-01-01T00:00:00Z",
    )
    job_dir = settings.jobs_dir / "expired"
    job_dir.mkdir(parents=True)
    (job_dir / "media.mp4").write_bytes(b"x")

    manager = JobManager(settings, fake_downloader)
    assert manager.sweep_expired() == 1
    assert jobs_repo.get_job(settings.db_path, "expired") is None
    assert not job_dir.exists()


def test_request_cancel_queued_is_immediate(tmp_path: Path, fake_downloader) -> None:
    settings = make_settings(tmp_path)
    init_db(settings.db_path)
    create_row(settings, "queued_job")
    manager = JobManager(settings, fake_downloader)

    row = manager.request_cancel("queued_job")
    assert row["status"] == "canceled"
    assert manager.request_cancel("queued_job")["status"] == "canceled"

    with pytest.raises(ApiError) as excinfo:
        manager.request_cancel("missing")
    assert excinfo.value.code == "job_not_found"


def test_request_cancel_completed_conflicts(tmp_path: Path, fake_downloader) -> None:
    settings = make_settings(tmp_path)
    init_db(settings.db_path)
    create_row(settings, "done")
    jobs_repo.mark_running(settings.db_path, "done", timeutil.iso())
    jobs_repo.complete_job(
        settings.db_path,
        "done",
        filename="a.mp4",
        size_bytes=1,
        content_type="video/mp4",
        finished_at=timeutil.iso(),
        expires_at="2099-01-01T00:00:00Z",
    )
    manager = JobManager(settings, fake_downloader)

    with pytest.raises(ApiError) as excinfo:
        manager.request_cancel("done")
    assert excinfo.value.code == "job_not_cancellable"


def make_request(tmp_path: Path, updates: list | None = None, cancel_event=None) -> DownloadRequest:
    return DownloadRequest(
        job_id="job",
        url="https://www.bilibili.com/video/BV1",
        quality="best",
        job_dir=tmp_path,
        cancel_event=cancel_event or threading.Event(),
        on_progress=(updates.append if updates is not None else (lambda update: None)),
        on_metadata=lambda title, thumbnail: None,
    )


def test_hooks_emit_download_progress(tmp_path: Path) -> None:
    updates: list = []
    hooks = _DownloadHooks(make_request(tmp_path, updates), timeout_seconds=60)

    hooks.on_progress(
        {
            "status": "downloading",
            "downloaded_bytes": 512,
            "total_bytes": 1024,
            "speed": 2048.0,
            "eta": 3,
            "info_dict": {"vcodec": "avc1"},
        }
    )
    update = updates[0]
    assert update.percent == 50.0
    assert update.stage == "video"
    assert update.phase == "downloading"
    assert update.speed_bps == 2048.0
    assert update.eta_seconds == 3


def test_hooks_detect_audio_stage(tmp_path: Path) -> None:
    updates: list = []
    hooks = _DownloadHooks(make_request(tmp_path, updates), timeout_seconds=60)
    hooks.on_progress(
        {
            "status": "downloading",
            "downloaded_bytes": 10,
            "total_bytes": 10,
            "info_dict": {"vcodec": "none"},
        }
    )
    assert updates[0].stage == "audio"


def test_hooks_emit_postprocessing_phase(tmp_path: Path) -> None:
    updates: list = []
    hooks = _DownloadHooks(make_request(tmp_path, updates), timeout_seconds=60)
    hooks.on_postprocessor({"status": "started"})
    assert updates[0].phase == "postprocessing"
    assert updates[0].percent is None


def test_hooks_abort_on_cancel_and_timeout(tmp_path: Path) -> None:
    event = threading.Event()
    event.set()
    hooks = _DownloadHooks(make_request(tmp_path, cancel_event=event), timeout_seconds=60)
    with pytest.raises(JobCancelled) as excinfo:
        hooks.on_progress({"status": "downloading"})
    assert excinfo.value.reason == "canceled"

    timed_out = _DownloadHooks(make_request(tmp_path), timeout_seconds=0)
    with pytest.raises(JobCancelled) as excinfo:
        timed_out.on_progress({"status": "downloading"})
    assert excinfo.value.reason == "timeout"
