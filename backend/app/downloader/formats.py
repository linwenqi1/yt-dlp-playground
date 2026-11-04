"""Quality ids, format selectors and height derivation from yt-dlp formats."""

from __future__ import annotations

from app.errors import ApiError

HEIGHTS = (2160, 1440, 1080, 720, 480, 360)
VIDEO_QUALITIES = tuple(f"{height}p" for height in HEIGHTS)
QUALITIES = ("best", *VIDEO_QUALITIES, "audio")


def quality_height(quality: str) -> int:
    try:
        return int(quality.removesuffix("p"))
    except ValueError as exc:
        raise ApiError(400, "invalid_quality") from exc


def validate_quality(quality: str) -> str:
    if quality not in QUALITIES:
        raise ApiError(400, "invalid_quality")
    return quality


def is_video_format(fmt: dict) -> bool:
    return fmt.get("vcodec") not in (None, "none") and bool(fmt.get("height"))


def has_audio_format(formats: list[dict]) -> bool:
    return any(fmt.get("acodec") not in (None, "none") for fmt in formats)


def derive_qualities(formats: list[dict]) -> list[dict]:
    """Return contract quality entries: best, real video heights, then audio."""
    heights = {int(fmt["height"]) for fmt in formats if is_video_format(fmt)}
    qualities: list[dict] = [{"id": "best", "kind": "video", "height": None}]
    qualities.extend(
        {"id": f"{height}p", "kind": "video", "height": height}
        for height in HEIGHTS
        if height in heights
    )
    if has_audio_format(formats):
        qualities.append({"id": "audio", "kind": "audio", "height": None})
    return qualities


def format_selector(quality: str) -> str:
    """Map a contract quality id to a yt-dlp format selector.

    Video qualities are upper bounds: asking for 1080p when only 720p exists
    downloads 720p.
    """
    validate_quality(quality)
    if quality == "audio":
        return "ba/b"
    if quality == "best":
        return "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b"
    height = quality_height(quality)
    return (
        f"bv*[height<={height}][ext=mp4]+ba[ext=m4a]"
        f"/bv*[height<={height}]+ba/b[height<={height}]/b[height<={height}]"
    )


def audio_postprocessors() -> list[dict]:
    return [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ]
