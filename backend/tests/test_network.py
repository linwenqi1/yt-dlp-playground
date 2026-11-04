"""Opt-in smoke tests against the real platforms.

Run with:
    YTP_NETWORK_TESTS=1 YTP_TEST_BILIBILI_URL=... uv run pytest -m network
"""

from __future__ import annotations

import os

import pytest

from app.config import Settings
from app.downloader.ytdlp import YtDlpDownloader

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(not os.getenv("YTP_NETWORK_TESTS"), reason="set YTP_NETWORK_TESTS=1"),
]


def test_bilibili_probe() -> None:
    url = os.getenv("YTP_TEST_BILIBILI_URL")
    if not url:
        pytest.skip("YTP_TEST_BILIBILI_URL not set")
    info = YtDlpDownloader(Settings(_env_file=None)).probe(url)
    assert info.platform == "bilibili"
    assert info.title
    assert info.qualities[0]["id"] == "best"


def test_youtube_probe() -> None:
    url = os.getenv("YTP_TEST_YOUTUBE_URL")
    if not url:
        pytest.skip("YTP_TEST_YOUTUBE_URL not set")
    info = YtDlpDownloader(Settings(_env_file=None)).probe(url)
    assert info.platform == "youtube"
    assert info.qualities[0]["id"] == "best"
