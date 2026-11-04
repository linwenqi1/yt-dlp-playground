from __future__ import annotations

from pathlib import Path

import pytest

from app.core import timeutil
from app.storage import jobs_repo
from app.storage.db import init_db

PROGRESS = {
    "percent": None,
    "downloaded_bytes": None,
    "total_bytes": None,
    "speed_bps": None,
    "eta_seconds": None,
    "stage": None,
}


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "jobs.db"
    init_db(path)
    return path


def create(db_path: Path, job_id: str = "job1", expires_at: str = "2099-01-01T00:00:00Z") -> None:
    jobs_repo.create_job(
        db_path,
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


def test_create_get_and_list(db_path: Path) -> None:
    create(db_path, "a")
    create(db_path, "b")

    row = jobs_repo.get_job(db_path, "a")
    assert row is not None
    assert row["status"] == "queued"
    assert row["quality"] == "720p"

    items = jobs_repo.list_jobs(db_path, limit=10)
    assert [item["id"] for item in items] == ["b", "a"]
    assert jobs_repo.get_job(db_path, "missing") is None


def test_mark_running_is_one_way(db_path: Path) -> None:
    create(db_path)
    assert jobs_repo.mark_running(db_path, "job1", timeutil.iso()) is True
    assert jobs_repo.mark_running(db_path, "job1", timeutil.iso()) is False
    assert jobs_repo.get_job(db_path, "job1")["status"] == "running"


def test_complete_requires_running(db_path: Path) -> None:
    create(db_path)
    assert (
        jobs_repo.complete_job(
            db_path,
            "job1",
            filename="a.mp4",
            size_bytes=10,
            content_type="video/mp4",
            finished_at=timeutil.iso(),
            expires_at="2099-01-01T00:00:00Z",
        )
        is False
    )
    jobs_repo.mark_running(db_path, "job1", timeutil.iso())
    assert (
        jobs_repo.complete_job(
            db_path,
            "job1",
            filename="a.mp4",
            size_bytes=10,
            content_type="video/mp4",
            finished_at=timeutil.iso(),
            expires_at="2099-01-01T00:00:00Z",
        )
        is True
    )
    row = jobs_repo.get_job(db_path, "job1")
    assert row["status"] == "completed"
    assert row["output_filename"] == "a.mp4"


def test_cancel_queued_only(db_path: Path) -> None:
    create(db_path)
    jobs_repo.mark_running(db_path, "job1", timeutil.iso())
    assert (
        jobs_repo.cancel_queued(
            db_path, "job1", finished_at=timeutil.iso(), expires_at="2099-01-01T00:00:00Z"
        )
        is False
    )
    jobs_repo.mark_cancel_requested(db_path, "job1")
    assert jobs_repo.get_job(db_path, "job1")["cancel_requested"] == 1
    assert (
        jobs_repo.cancel_job(
            db_path, "job1", finished_at=timeutil.iso(), expires_at="2099-01-01T00:00:00Z"
        )
        is True
    )
    assert jobs_repo.get_job(db_path, "job1")["status"] == "canceled"


def test_delete_expired_only_removes_terminal_and_expired(db_path: Path) -> None:
    create(db_path, "expired_completed", expires_at="2000-01-01T00:00:00Z")
    jobs_repo.mark_running(db_path, "expired_completed", timeutil.iso())
    jobs_repo.complete_job(
        db_path,
        "expired_completed",
        filename="a.mp4",
        size_bytes=1,
        content_type="video/mp4",
        finished_at=timeutil.iso(),
        expires_at="2000-01-01T00:00:00Z",
    )
    create(db_path, "expired_queued", expires_at="2000-01-01T00:00:00Z")
    create(db_path, "future", expires_at="2099-01-01T00:00:00Z")

    removed = jobs_repo.delete_expired(db_path, timeutil.iso())
    assert [row["id"] for row in removed] == ["expired_completed"]
    assert jobs_repo.get_job(db_path, "expired_completed") is None
    assert jobs_repo.get_job(db_path, "expired_queued") is not None
    assert jobs_repo.get_job(db_path, "future") is not None


def test_recover_active_marks_interrupted(db_path: Path) -> None:
    create(db_path, "queued_job")
    create(db_path, "running_job")
    jobs_repo.mark_running(db_path, "running_job", timeutil.iso())
    create(db_path, "completed_job")
    jobs_repo.mark_running(db_path, "completed_job", timeutil.iso())
    jobs_repo.complete_job(
        db_path,
        "completed_job",
        filename="a.mp4",
        size_bytes=1,
        content_type="video/mp4",
        finished_at=timeutil.iso(),
        expires_at="2099-01-01T00:00:00Z",
    )

    rows = jobs_repo.recover_active(
        db_path,
        {"code": "interrupted", "message": "服务重启，任务已中断", "details": None},
        finished_at=timeutil.iso(),
        expires_at="2099-01-01T00:00:00Z",
    )
    assert {row["id"] for row in rows} == {"queued_job", "running_job"}
    for job_id in ("queued_job", "running_job"):
        row = jobs_repo.get_job(db_path, job_id)
        assert row["status"] == "failed"
        assert "interrupted" in row["error_json"]
    assert jobs_repo.get_job(db_path, "completed_job")["status"] == "completed"


def test_delete_job(db_path: Path) -> None:
    create(db_path)
    assert jobs_repo.delete_job(db_path, "job1") is True
    assert jobs_repo.delete_job(db_path, "job1") is False
    assert jobs_repo.count_status(db_path, "queued") == 0
