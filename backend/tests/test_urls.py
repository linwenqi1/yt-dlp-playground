from __future__ import annotations

import pytest

from app.core.urls import normalize_url
from app.errors import ApiError


@pytest.mark.parametrize(
    ("raw", "expected_platform"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://youtu.be/dQw4w9WgXcQ", "youtube"),
        ("https://music.youtube.com/watch?v=abc", "youtube"),
        ("https://www.bilibili.com/video/BV1xx411c7mD", "bilibili"),
        ("https://bilibili.com/video/BV1xx411c7mD?p=2", "bilibili"),
        ("https://m.bilibili.com/video/BV1xx411c7mD", "bilibili"),
    ],
)
def test_accepts_supported_hosts(raw: str, expected_platform: str) -> None:
    normalized = normalize_url(raw)
    assert normalized.platform == expected_platform
    assert normalized.url.startswith("https://")


def test_strips_tracking_params_and_fragment() -> None:
    normalized = normalize_url(
        "https://www.bilibili.com/video/BV1xx411c7mD?p=2&spm_id_from=333.999&vd_source=x#t=30"
    )
    assert normalized.url == "https://www.bilibili.com/video/BV1xx411c7mD?p=2"


@pytest.mark.parametrize("locale", ["zh-Hans", "zh-Hant", "zh-CN", "en", "ja"])
def test_strips_bilibili_locale_prefix(locale: str) -> None:
    normalized = normalize_url(
        f"https://www.bilibili.com/{locale}/video/BV1zpxg6tEpU/?vd_source=abc"
    )
    assert normalized.url == "https://www.bilibili.com/video/BV1zpxg6tEpU/"
    assert normalized.platform == "bilibili"


def test_keeps_bilibili_path_without_locale() -> None:
    normalized = normalize_url("https://www.bilibili.com/video/BV1xx411c7mD")
    assert normalized.url == "https://www.bilibili.com/video/BV1xx411c7mD"


def test_does_not_strip_locale_looking_segment_elsewhere() -> None:
    normalized = normalize_url("https://www.bilibili.com/list/watchlater?bvid=BV1xx411c7mD")
    assert "/list/watchlater" in normalized.url


def test_drops_trailing_dot_host() -> None:
    normalized = normalize_url("https://www.youtube.com./watch?v=x")
    assert normalized.url.startswith("https://www.youtube.com/")


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("", "invalid_url"),
        ("   ", "invalid_url"),
        ("ftp://www.youtube.com/watch?v=x", "invalid_url"),
        ("https://user:pass@www.youtube.com/watch?v=x", "invalid_url"),
        ("https://www.youtube.com:8443/watch?v=x", "invalid_url"),
        ("http://127.0.0.1/video", "invalid_url"),
        ("http://[::1]/video", "invalid_url"),
        ("https://youtube.com.evil.com/watch?v=x", "unsupported_site"),
        ("https://vimeo.com/123", "unsupported_site"),
        ("https://b23.tv/abc", "unsupported_site"),
        ("https://www.bilibili.com/video/" + "a" * 3000, "invalid_url"),
        ("https://www.youtube.com/watch?v=x\nhttps://evil.com", "invalid_url"),
    ],
)
def test_rejects_unsafe_or_unsupported_urls(raw: str, code: str) -> None:
    with pytest.raises(ApiError) as excinfo:
        normalize_url(raw)
    assert excinfo.value.code == code


def test_b23_short_link_message_mentions_expansion() -> None:
    with pytest.raises(ApiError) as excinfo:
        normalize_url("https://b23.tv/abc")
    assert "bilibili.com" in str(excinfo.value)
