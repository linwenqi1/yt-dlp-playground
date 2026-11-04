from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from app.api.deps import no_store, require_token
from app.core.urls import normalize_url
from app.schemas import InfoOut, InfoRequest

router = APIRouter(dependencies=[Depends(require_token), Depends(no_store)])


@router.post("/info", response_model=InfoOut)
async def extract_info(payload: InfoRequest, request: Request) -> dict[str, Any]:
    normalized = normalize_url(payload.url)
    semaphore: asyncio.Semaphore = request.app.state.info_semaphore
    async with semaphore:
        video = await run_in_threadpool(request.app.state.downloader.probe, normalized.url)
    return {
        "url": normalized.url,
        "platform": normalized.platform,
        "video_id": video.video_id,
        "title": video.title,
        "uploader": video.uploader,
        "duration_seconds": video.duration_seconds,
        "thumbnail_url": video.thumbnail_url,
        "webpage_url": video.webpage_url,
        "qualities": video.qualities,
    }
