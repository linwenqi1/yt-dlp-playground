from __future__ import annotations

import pytest

from app.downloader.formats import (
    audio_postprocessors,
    derive_qualities,
    format_selector,
    validate_quality,
)
from app.errors import ApiError


def fmt(
    height: int | None = None, vcodec: str | None = "avc1", acodec: str | None = "none"
) -> dict:
    return {"height": height, "vcodec": vcodec, "acodec": acodec}


def test_derive_qualities_lists_only_real_heights() -> None:
    qualities = derive_qualities(
        [
            fmt(1080),
            fmt(720),
            fmt(480),
            fmt(None, vcodec="none", acodec="mp4a"),
        ]
    )
    assert [item["id"] for item in qualities] == ["best", "1080p", "720p", "480p", "audio"]


def test_derive_qualities_ignores_heights_outside_contract() -> None:
    qualities = derive_qualities([fmt(1440), fmt(576), fmt(None, vcodec="none", acodec="mp4a")])
    assert [item["id"] for item in qualities] == ["best", "1440p", "audio"]


def test_derive_qualities_without_audio() -> None:
    qualities = derive_qualities([fmt(360)])
    assert [item["id"] for item in qualities] == ["best", "360p"]


def test_derive_qualities_empty_formats() -> None:
    assert derive_qualities([]) == [{"id": "best", "kind": "video", "height": None}]


@pytest.mark.parametrize(
    ("quality", "expected_fragment"),
    [
        ("best", "bv*[ext=mp4]+ba[ext=m4a]"),
        ("720p", "height<=720"),
        ("2160p", "height<=2160"),
        ("audio", "ba/b"),
    ],
)
def test_format_selector(quality: str, expected_fragment: str) -> None:
    assert expected_fragment in format_selector(quality)


def test_invalid_quality_rejected() -> None:
    with pytest.raises(ApiError) as excinfo:
        validate_quality("4k")
    assert excinfo.value.code == "invalid_quality"


def test_audio_postprocessors_extract_mp3() -> None:
    processors = audio_postprocessors()
    assert processors[0]["key"] == "FFmpegExtractAudio"
    assert processors[0]["preferredcodec"] == "mp3"
