from __future__ import annotations

from fastapi.testclient import TestClient

from app.errors import ApiError
from app.main import create_app
from tests.conftest import make_settings

URL = "https://www.bilibili.com/video/BV1xx411c7mD"


def test_info_returns_contract_shape(client) -> None:
    response = client.post("/api/v1/info", json={"url": f"{URL}?spm_id_from=333.999"})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body == {
        "url": URL,
        "platform": "bilibili",
        "video_id": "BV1xx411c7mD",
        "title": "示例视频",
        "uploader": "示例UP主",
        "duration_seconds": 123,
        "thumbnail_url": "https://example.com/cover.jpg",
        "webpage_url": URL,
        "qualities": [
            {"id": "best", "kind": "video", "height": None},
            {"id": "720p", "kind": "video", "height": 720},
            {"id": "audio", "kind": "audio", "height": None},
        ],
    }


def test_info_rejects_unsupported_site(client) -> None:
    response = client.post("/api/v1/info", json={"url": "https://vimeo.com/1"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_site"


def test_info_rejects_invalid_url(client) -> None:
    response = client.post("/api/v1/info", json={"url": "not a url"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_url"


def test_info_maps_extraction_errors(client, fake_downloader) -> None:
    fake_downloader.probe_error = ApiError(422, "login_required")
    response = client.post("/api/v1/info", json={"url": URL})
    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "login_required",
        "message": "平台要求登录或验证，请配置 cookies 后重试",
        "details": None,
    }


def test_info_validation_error_uses_envelope(client) -> None:
    response = client.post("/api/v1/info", json={})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_health_reports_runtime(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["yt_dlp_version"]
    assert isinstance(body["ffmpeg_available"], bool)
    assert body["queue_depth"] == 0
    assert body["active_jobs"] == 0


def test_token_is_enforced_when_configured(tmp_path, fake_downloader) -> None:
    settings = make_settings(tmp_path, api_token="secret")
    app = create_app(settings, fake_downloader)
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200

        missing = client.post("/api/v1/info", json={"url": URL})
        assert missing.status_code == 401
        assert missing.json()["error"]["code"] == "unauthorized"

        wrong = client.post("/api/v1/info", json={"url": URL}, headers={"X-API-Token": "nope"})
        assert wrong.status_code == 401

        ok = client.post("/api/v1/info", json={"url": URL}, headers={"X-API-Token": "secret"})
        assert ok.status_code == 200
