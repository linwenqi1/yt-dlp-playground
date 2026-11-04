"""Contract error envelope and mapping of yt-dlp failures to stable error codes."""

from __future__ import annotations

from typing import Any

ERROR_MESSAGES: dict[str, str] = {
    "invalid_request": "请求参数不正确",
    "invalid_url": "链接格式不正确",
    "unsupported_site": "仅支持 YouTube 和 Bilibili 链接",
    "invalid_quality": "不支持的清晰度",
    "unauthorized": "未授权：缺少或错误的 API token",
    "job_not_found": "任务不存在",
    "job_not_cancellable": "任务已结束，无法取消",
    "job_not_deletable": "任务进行中，无法删除",
    "file_not_ready": "文件尚未准备好",
    "file_gone": "文件已不存在或已过期",
    "video_unavailable": "视频不可用：可能已删除、被隐藏或链接有误",
    "video_private": "视频为私密内容，无法下载",
    "login_required": "平台要求登录或验证，请配置 cookies 后重试",
    "age_restricted": "视频有年龄限制，需要登录 cookies",
    "region_blocked": "视频在当前网络区域不可用",
    "live_stream_unsupported": "暂不支持直播",
    "playlist_not_supported": "暂不支持播放列表或多 P 视频，请粘贴单个视频链接",
    "format_unavailable": "没有匹配的清晰度，请换一个选项",
    "internal_error": "服务器内部错误",
    "extraction_failed": "解析视频信息失败",
    "upstream_unavailable": "上游平台暂时不可用",
    "queue_full": "下载队列已满，请稍后重试",
    "insufficient_storage": "服务器磁盘空间不足",
    "download_failed": "下载失败",
    "merge_failed": "音视频合并失败",
    "file_too_large": "文件超过大小限制",
    "timeout": "任务超时",
    "interrupted": "服务重启，任务已中断",
}

_DEFAULT_STATUS: dict[str, int] = {
    "video_unavailable": 422,
    "video_private": 422,
    "login_required": 422,
    "age_restricted": 422,
    "region_blocked": 422,
    "live_stream_unsupported": 422,
    "playlist_not_supported": 422,
    "format_unavailable": 422,
    "extraction_failed": 502,
    "upstream_unavailable": 502,
    "internal_error": 500,
}


class ApiError(Exception):
    """An error that is safe to expose to clients."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.details = details
        self.headers = headers
        super().__init__(message or ERROR_MESSAGES.get(code, "请求失败"))

    def to_detail(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "details": self.details}


def error_detail(code: str, message: str | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message or ERROR_MESSAGES.get(code, "请求失败"),
        "details": None,
    }


# (needles, code) — checked in order; first match wins.
_PATTERNS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("sign in to confirm", "confirm you're not a bot", "confirm you’re not a bot"),
        "login_required",
    ),
    (("login required", "log in to", "use --cookies", "cookies"), "login_required"),
    (("http error 403", "http error 412", "http error 429"), "login_required"),
    (("private video", "video is private", "this video is private"), "video_private"),
    (("age-restricted", "age restricted", "confirm your age"), "age_restricted"),
    (
        (
            "not available in your country",
            "available in your country",
            "geo restrict",
            "geo-restrict",
        ),
        "region_blocked",
    ),
    (("requested format is not available", "no video formats found"), "format_unavailable"),
    (("http error 404", "http error 410"), "video_unavailable"),
    (
        ("video unavailable", "is unavailable", "has been removed", "does not exist"),
        "video_unavailable",
    ),
    (
        ("timed out", "connection reset", "temporary failure", "name resolution"),
        "upstream_unavailable",
    ),
    (("unable to download", "unable to extract"), "extraction_failed"),
)


def map_ytdlp_error(message: str, *, context: str = "info") -> ApiError:
    """Map an arbitrary yt-dlp error message to a safe ApiError.

    The raw message is never returned to clients: it may contain URLs, local paths
    or ANSI control sequences.
    """
    text = (message or "").lower()
    for needles, code in _PATTERNS:
        if any(needle in text for needle in needles):
            status = _DEFAULT_STATUS.get(code, 502)
            if context == "job" and status == 502:
                code, status = "download_failed", 500
            return ApiError(status, code)
    if context == "job":
        return ApiError(500, "download_failed")
    return ApiError(502, "extraction_failed")
