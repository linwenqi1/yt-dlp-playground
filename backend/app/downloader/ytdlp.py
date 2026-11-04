"""The only module that talks to yt-dlp. Exposes probe() and download()."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.config import Settings
from app.core.urls import normalize_url
from app.downloader.base import (
    DownloadRequest,
    DownloadResult,
    JobCancelled,
    ProgressUpdate,
    VideoInfo,
)
from app.downloader.formats import audio_postprocessors, derive_qualities, format_selector
from app.errors import ApiError, map_ytdlp_error
from app.storage import files

logger = logging.getLogger(__name__)


class _YdlLogger:
    """Route yt-dlp output into the application logger, never to stdout."""

    def debug(self, message: str) -> None:
        logger.debug("%s", message)

    def info(self, message: str) -> None:
        logger.debug("%s", message)

    def warning(self, message: str) -> None:
        logger.warning("%s", message)

    def error(self, message: str) -> None:
        logger.warning("%s", message)


class InfoCache:
    def __init__(self, ttl_seconds: int, maxsize: int = 128) -> None:
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._items: OrderedDict[str, tuple[float, VideoInfo]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> VideoInfo | None:
        if self._ttl <= 0:
            return None
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            stored_at, value = item
            if time.monotonic() - stored_at > self._ttl:
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return value

    def put(self, key: str, value: VideoInfo) -> None:
        if self._ttl <= 0:
            return
        with self._lock:
            self._items[key] = (time.monotonic(), value)
            self._items.move_to_end(key)
            while len(self._items) > self._maxsize:
                self._items.popitem(last=False)


def _expected_bytes(raw: Any) -> int | None:
    """Best-effort size of the selected streams.

    yt-dlp silently skips formats larger than ``max_filesize`` (no exception,
    no output file), so this is used to tell "too large" from other failures.
    """
    if not isinstance(raw, dict):
        return None
    formats = [fmt for fmt in raw.get("requested_formats") or [] if isinstance(fmt, dict)]
    if formats:
        total = 0
        for fmt in formats:
            size = fmt.get("filesize") or fmt.get("filesize_approx")
            if not isinstance(size, int) or size <= 0:
                return None
            total += size
        return total
    downloads = [item for item in raw.get("requested_downloads") or [] if isinstance(item, dict)]
    candidates = downloads[:1] + [raw]
    for item in candidates:
        size = item.get("filesize") or item.get("filesize_approx")
        if isinstance(size, int) and size > 0:
            return size
    return None


class YtDlpDownloader:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache = InfoCache(settings.info_cache_ttl_seconds)

    def cached_info(self, url: str) -> VideoInfo | None:
        return self.cache.get(url)

    def probe(self, url: str) -> VideoInfo:
        cached = self.cache.get(url)
        if cached is not None:
            return cached
        with self._cookie_copy() as cookiefile:
            opts = self._base_opts()
            if cookiefile is not None:
                opts["cookiefile"] = str(cookiefile)
            try:
                with YoutubeDL(opts) as ydl:
                    raw = ydl.extract_info(url, download=False)
            except DownloadError as exc:
                raise map_ytdlp_error(str(exc), context="info") from exc
            except Exception as exc:  # noqa: BLE001 - never leak raw errors
                logger.exception("info extraction crashed for %s", url)
                raise ApiError(502, "extraction_failed") from exc
        info = self._to_video_info(url, raw)
        self.cache.put(url, info)
        return info

    def download(self, request: DownloadRequest) -> DownloadResult:
        files.prepare_job_dir(request.job_dir)
        hooks = _DownloadHooks(request, timeout_seconds=self.settings.max_job_minutes * 60)
        opts = self._base_opts()
        opts.update(
            {
                "format": format_selector(request.quality),
                "outtmpl": "media.%(ext)s",
                "paths": {
                    "home": str(request.job_dir),
                    "temp": str(request.job_dir / ".tmp"),
                },
                "progress_hooks": [hooks.on_progress],
                "postprocessor_hooks": [hooks.on_postprocessor],
                "max_filesize": self.settings.max_filesize_bytes,
                "overwrites": True,
            }
        )
        if request.quality == "audio":
            opts["postprocessors"] = audio_postprocessors()

        title: str | None = None
        thumbnail: str | None = None
        try:
            with self._cookie_copy() as cookiefile:
                if cookiefile is not None:
                    opts["cookiefile"] = str(cookiefile)
                with YoutubeDL(opts) as ydl:
                    raw = ydl.extract_info(request.url, download=True)
            if isinstance(raw, dict):
                title = raw.get("title")
                thumbnail = raw.get("thumbnail")
                request.on_metadata(title, thumbnail)
        except JobCancelled:
            raise
        except DownloadError as exc:
            message = str(exc).lower()
            if "max-filesize" in message or "max_filesize" in message:
                raise ApiError(500, "file_too_large") from exc
            if "ffmpeg" in message and ("merge" in message or "postprocess" in message):
                raise ApiError(500, "merge_failed") from exc
            raise map_ytdlp_error(str(exc), context="job") from exc
        except ApiError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("download crashed for job %s", request.job_id)
            raise ApiError(500, "download_failed") from exc

        output = files.find_output(request.job_dir)
        if output is None:
            # yt-dlp skips oversized formats silently instead of raising.
            expected = _expected_bytes(raw)
            if expected is not None and expected > self.settings.max_filesize_bytes:
                raise ApiError(500, "file_too_large")
            logger.error("job %s finished without a media file", request.job_id)
            raise ApiError(500, "download_failed")
        size = output.stat().st_size
        if size > self.settings.max_filesize_bytes:
            output.unlink(missing_ok=True)
            raise ApiError(500, "file_too_large")
        return DownloadResult(path=output, title=title, thumbnail_url=thumbnail)

    def _to_video_info(self, url: str, raw: Any) -> VideoInfo:
        if not isinstance(raw, dict):
            raise ApiError(502, "extraction_failed")
        if raw.get("_type") in {"playlist", "multi_video"} or raw.get("entries"):
            raise ApiError(422, "playlist_not_supported")
        if raw.get("is_live") or raw.get("live_status") in {"is_live", "is_upcoming"}:
            raise ApiError(422, "live_stream_unsupported")
        formats = [fmt for fmt in raw.get("formats") or [] if isinstance(fmt, dict)]
        platform = normalize_url(url).platform
        duration = raw.get("duration")
        return VideoInfo(
            url=url,
            platform=platform,
            video_id=str(raw.get("id") or ""),
            title=str(raw.get("title") or raw.get("id") or "未命名视频"),
            uploader=raw.get("uploader") or raw.get("channel") or raw.get("uploader_id"),
            duration_seconds=int(duration) if isinstance(duration, (int, float)) else None,
            thumbnail_url=raw.get("thumbnail"),
            webpage_url=raw.get("webpage_url") or url,
            qualities=derive_qualities(formats),
        )

    def _base_opts(self) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "cachedir": False,
            "logger": _YdlLogger(),
            "socket_timeout": 20,
            "retries": 3,
            "extractor_retries": 1,
            "concurrent_fragment_downloads": 4,
            "js_runtimes": {"deno": {}, "node": {}},
        }
        if self.settings.proxy:
            opts["proxy"] = self.settings.proxy
        if self.settings.impersonate:
            opts["impersonate"] = self.settings.impersonate
        return opts

    @contextmanager
    def _cookie_copy(self) -> Iterator[Path | None]:
        """Copy cookies to a private temp file so yt-dlp never rewrites the original."""
        source = self.settings.cookies_file
        if source is None:
            yield None
            return
        if not source.is_file():
            logger.warning("configured cookies file does not exist: %s", source)
            yield None
            return
        file_descriptor, name = tempfile.mkstemp(prefix="ytp-cookies-", suffix=".txt")
        os.close(file_descriptor)
        temp_path = Path(name)
        try:
            shutil.copyfile(source, temp_path)
            os.chmod(temp_path, 0o600)
            yield temp_path
        finally:
            temp_path.unlink(missing_ok=True)


class _DownloadHooks:
    def __init__(self, request: DownloadRequest, timeout_seconds: int) -> None:
        self.request = request
        self.started_at = time.monotonic()
        self.timeout_seconds = timeout_seconds

    def _check_abort(self) -> None:
        if self.request.cancel_event.is_set():
            raise JobCancelled("canceled")
        if time.monotonic() - self.started_at > self.timeout_seconds:
            raise JobCancelled("timeout")

    def on_progress(self, data: dict[str, Any]) -> None:
        self._check_abort()
        if data.get("status") != "downloading":
            return
        downloaded = data.get("downloaded_bytes")
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        percent = None
        if downloaded is not None and total:
            percent = round(downloaded * 100.0 / total, 1)
        info = data.get("info_dict") or {}
        stage = "video" if info.get("vcodec") not in (None, "none") else "audio"
        eta = data.get("eta")
        self.request.on_progress(
            ProgressUpdate(
                percent=percent,
                downloaded_bytes=int(downloaded) if downloaded is not None else None,
                total_bytes=int(total) if total else None,
                speed_bps=float(data["speed"]) if data.get("speed") else None,
                eta_seconds=int(eta) if eta is not None else None,
                stage=stage,
                phase="downloading",
            )
        )

    def on_postprocessor(self, data: dict[str, Any]) -> None:
        self._check_abort()
        if data.get("status") == "started":
            self.request.on_progress(ProgressUpdate(phase="postprocessing"))
