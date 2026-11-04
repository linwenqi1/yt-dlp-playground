"""Strict URL policy: exact host allowlist, no userinfo/ports/IP literals."""

from __future__ import annotations

import ipaddress
import re
from typing import NamedTuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.errors import ApiError

YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
    }
)
BILIBILI_HOSTS = frozenset({"bilibili.com", "www.bilibili.com", "m.bilibili.com"})
SUPPORTED_HOSTS = YOUTUBE_HOSTS | BILIBILI_HOSTS

# Share/session tracking parameters; irrelevant for extraction and cache identity.
TRACKING_PARAMS = frozenset(
    {"spm_id_from", "vd_source", "share_source", "share_medium", "si", "feature"}
)
MAX_URL_LENGTH = 2048

# Bilibili serves locale-prefixed pages like /zh-Hans/video/BV...; the
# dedicated extractor only matches /video/BV..., so strip the locale segment.
BILIBILI_LOCALE_VIDEO = re.compile(r"^/[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?/video/")


class NormalizedUrl(NamedTuple):
    url: str
    platform: str


def normalize_url(raw: str) -> NormalizedUrl:
    value = (raw or "").strip()
    if not value:
        raise ApiError(400, "invalid_url", "请输入视频链接")
    if len(value) > MAX_URL_LENGTH:
        raise ApiError(400, "invalid_url", "链接过长")
    if any(char in value for char in ("\n", "\r", "\x00")):
        raise ApiError(400, "invalid_url", "链接包含非法字符")

    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise ApiError(400, "invalid_url") from exc

    if parts.scheme not in {"http", "https"}:
        raise ApiError(400, "invalid_url", "只接受 http/https 链接")
    if parts.username or parts.password:
        raise ApiError(400, "invalid_url", "链接不能包含用户名或密码")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise ApiError(400, "invalid_url", "链接缺少域名")
    if _is_ip_literal(host):
        raise ApiError(400, "invalid_url", "不接受 IP 地址链接")

    default_port = 80 if parts.scheme == "http" else 443
    try:
        port = parts.port
    except ValueError as exc:
        raise ApiError(400, "invalid_url", "端口不正确") from exc
    if port is not None and port != default_port:
        raise ApiError(400, "invalid_url", "不接受非默认端口")

    if host not in SUPPORTED_HOSTS:
        if host == "b23.tv":
            raise ApiError(
                400,
                "unsupported_site",
                "暂不支持 b23.tv 短链，请先展开为 bilibili.com 链接",
            )
        raise ApiError(400, "unsupported_site")

    query = _strip_tracking(parts.query)
    platform = "youtube" if host in YOUTUBE_HOSTS else "bilibili"
    path = parts.path or "/"
    if platform == "bilibili":
        match = BILIBILI_LOCALE_VIDEO.match(path)
        if match:
            path = "/video/" + path[match.end() :]
    canonical = urlunsplit((parts.scheme, host, path, query, ""))
    return NormalizedUrl(canonical, platform)


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _strip_tracking(query: str) -> str:
    if not query:
        return ""
    pairs = [
        (key, value)
        for key, value in parse_qsl(query, keep_blank_values=True)
        if not key.startswith("utm_") and key not in TRACKING_PARAMS
    ]
    return urlencode(pairs)
