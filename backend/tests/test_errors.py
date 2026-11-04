from __future__ import annotations

import pytest

from app.errors import ApiError, map_ytdlp_error


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("ERROR: Sign in to confirm you're not a bot", "login_required"),
        ("ERROR: Private video. Sign in if you've been granted access", "video_private"),
        ("ERROR: This video is unavailable", "video_unavailable"),
        ("ERROR: This video is age-restricted", "age_restricted"),
        ("ERROR: The uploader has not made this video available in your country", "region_blocked"),
        ("ERROR: Requested format is not available", "format_unavailable"),
        ("ERROR: HTTP Error 412: Precondition Failed", "login_required"),
    ],
)
def test_maps_known_failures(message: str, code: str) -> None:
    assert map_ytdlp_error(message).code == code


def test_unknown_failure_is_safe_and_generic() -> None:
    error = map_ytdlp_error("ERROR: <urlopen error secret-path /srv/data>")
    assert error.code == "extraction_failed"
    assert "secret-path" not in str(error)
    assert error.status_code == 502


def test_job_context_uses_download_failed() -> None:
    error = map_ytdlp_error("something odd happened", context="job")
    assert error.code == "download_failed"
    assert error.status_code == 500


def test_api_error_default_message() -> None:
    error = ApiError(404, "job_not_found")
    assert str(error) == "任务不存在"
    assert error.to_detail() == {"code": "job_not_found", "message": "任务不存在", "details": None}
