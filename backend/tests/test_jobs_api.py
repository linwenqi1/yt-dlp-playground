from __future__ import annotations

import time

URL = "https://www.bilibili.com/video/BV1xx411c7mD"


def wait_for(client, job_id: str, statuses: set[str], timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        last = response.json()
        if last["status"] in statuses:
            return last
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not reach {statuses}; last={last}")


def create_job(client, quality: str = "720p"):
    response = client.post("/api/v1/jobs", json={"url": URL, "quality": quality})
    assert response.status_code == 201, response.text
    return response.json(), response.headers


def test_create_and_complete_job(client, fake_downloader) -> None:
    created, headers = create_job(client)

    assert headers["location"] == f"/api/v1/jobs/{created['id']}"
    assert created["status"] in {"queued", "running"}
    assert created["quality"] == "720p"
    assert created["platform"] == "bilibili"
    assert "percent" in created["progress"]

    job = wait_for(client, created["id"], {"completed"})
    assert job["progress"]["percent"] == 100.0
    assert job["file"] == {
        "name": "示例标题.mp4",
        "size_bytes": len(fake_downloader.payload),
        "content_type": "video/mp4",
    }
    assert job["title"] == "示例标题"
    assert job["error"] is None
    assert job["finished_at"]
    assert job["expires_at"] > job["finished_at"]


def test_list_jobs_newest_first(client) -> None:
    first, _ = create_job(client)
    wait_for(client, first["id"], {"completed", "failed", "canceled"})
    second, _ = create_job(client)
    wait_for(client, second["id"], {"completed", "failed", "canceled"})

    response = client.get("/api/v1/jobs?limit=10")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items][:2] == [second["id"], first["id"]]


def test_file_download_and_range(client, fake_downloader) -> None:
    created, _ = create_job(client)
    wait_for(client, created["id"], {"completed"})
    path = f"/api/v1/jobs/{created['id']}/file"

    full = client.get(path)
    assert full.status_code == 200
    assert full.content == fake_downloader.payload
    assert full.headers["accept-ranges"] == "bytes"
    assert "filename*=utf-8''" in full.headers["content-disposition"]
    assert full.headers["cache-control"] == "private, max-age=0"

    partial = client.get(path, headers={"Range": "bytes=0-9"})
    assert partial.status_code == 206
    assert len(partial.content) == 10
    assert partial.headers["content-range"] == f"bytes 0-9/{len(fake_downloader.payload)}"


def test_file_not_ready_while_running(client, fake_downloader) -> None:
    fake_downloader.block_until_released = True
    created, _ = create_job(client)
    assert fake_downloader.entered.wait(2)

    response = client.get(f"/api/v1/jobs/{created['id']}/file")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "file_not_ready"

    fake_downloader.release.set()
    wait_for(client, created["id"], {"completed"})


def test_cancel_queued_job(client, fake_downloader) -> None:
    fake_downloader.block_until_released = True
    first, _ = create_job(client)
    assert fake_downloader.entered.wait(2)
    second, _ = create_job(client)

    response = client.post(f"/api/v1/jobs/{second['id']}/cancel")
    assert response.status_code == 202
    assert response.json()["status"] == "canceled"
    assert response.json()["cancel_requested"] is True

    fake_downloader.release.set()
    wait_for(client, first["id"], {"completed"})
    assert wait_for(client, second["id"], {"canceled"})["file"] is None


def test_cancel_running_job(client, fake_downloader) -> None:
    fake_downloader.block_until_released = True
    created, _ = create_job(client)
    assert fake_downloader.entered.wait(2)

    response = client.post(f"/api/v1/jobs/{created['id']}/cancel")
    assert response.status_code == 202
    assert response.json()["cancel_requested"] is True

    job = wait_for(client, created["id"], {"canceled"})
    assert job["file"] is None

    again = client.post(f"/api/v1/jobs/{created['id']}/cancel")
    assert again.status_code == 202
    assert again.json()["status"] == "canceled"


def test_cancel_finished_job_conflicts(client) -> None:
    created, _ = create_job(client)
    wait_for(client, created["id"], {"completed"})

    response = client.post(f"/api/v1/jobs/{created['id']}/cancel")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "job_not_cancellable"


def test_delete_running_job_conflicts_and_completed_succeeds(
    client, fake_downloader, settings
) -> None:
    fake_downloader.block_until_released = True
    created, _ = create_job(client)
    assert fake_downloader.entered.wait(2)

    conflict = client.delete(f"/api/v1/jobs/{created['id']}")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "job_not_deletable"

    fake_downloader.release.set()
    wait_for(client, created["id"], {"completed"})
    job_dir = settings.jobs_dir / created["id"]
    assert job_dir.exists()

    deleted = client.delete(f"/api/v1/jobs/{created['id']}")
    assert deleted.status_code == 204
    assert not job_dir.exists()
    assert client.get(f"/api/v1/jobs/{created['id']}").status_code == 404


def test_unknown_job_returns_404(client) -> None:
    for method, path in (
        ("get", "/api/v1/jobs/does-not-exist"),
        ("delete", "/api/v1/jobs/does-not-exist"),
        ("post", "/api/v1/jobs/does-not-exist/cancel"),
        ("get", "/api/v1/jobs/does-not-exist/file"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 404, (method, path)
        assert response.json()["error"]["code"] == "job_not_found"


def test_invalid_quality_rejected(client) -> None:
    response = client.post("/api/v1/jobs", json={"url": URL, "quality": "4k"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_quality"


def test_queue_full_returns_503(client, fake_downloader) -> None:
    fake_downloader.block_until_released = True
    first, _ = create_job(client)
    assert fake_downloader.entered.wait(2)
    create_job(client)  # fills the single queue slot

    rejected = client.post("/api/v1/jobs", json={"url": URL, "quality": "best"})
    assert rejected.status_code == 503
    assert rejected.json()["error"]["code"] == "queue_full"
    assert rejected.headers["retry-after"] == "10"

    fake_downloader.release.set()
    wait_for(client, first["id"], {"completed"})


def test_job_failure_is_reported_safely(client, fake_downloader) -> None:
    from app.errors import ApiError

    fake_downloader.download_error = ApiError(500, "download_failed")
    created, _ = create_job(client)
    job = wait_for(client, created["id"], {"failed"})
    assert job["error"]["code"] == "download_failed"
    assert job["file"] is None


def test_limit_validation_uses_envelope(client) -> None:
    response = client.get("/api/v1/jobs?limit=0")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
