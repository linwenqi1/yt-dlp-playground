from __future__ import annotations

import asyncio
import logging
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.router import api_router
from app.config import Settings
from app.downloader.base import Downloader
from app.downloader.manager import JobManager
from app.downloader.ytdlp import YtDlpDownloader
from app.errors import ERROR_MESSAGES, ApiError
from app.storage.db import init_db

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    code: str,
    message: str | None = None,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    merged_headers = {"Cache-Control": "no-store"}
    if headers:
        merged_headers.update(headers)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message or ERROR_MESSAGES.get(code, "请求失败"),
                "details": details,
            }
        },
        headers=merged_headers,
    )


def create_app(settings: Settings | None = None, downloader: Downloader | None = None) -> FastAPI:
    app_settings = settings or Settings()
    logging.basicConfig(
        level=app_settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app_settings.ensure_dirs()
        init_db(app_settings.db_path)
        if shutil.which("ffmpeg") is None:
            logger.warning("ffmpeg not found on PATH; merging and audio extraction will fail")
        if shutil.which("deno") is None and shutil.which("node") is None:
            logger.warning("no JS runtime (deno/node) found; YouTube extraction may be degraded")

        active_downloader = downloader if downloader is not None else YtDlpDownloader(app_settings)
        manager = JobManager(app_settings, active_downloader)
        app.state.settings = app_settings
        app.state.downloader = active_downloader
        app.state.manager = manager
        app.state.info_semaphore = asyncio.Semaphore(app_settings.info_concurrency)
        manager.start()
        try:
            yield
        finally:
            manager.stop()

    app = FastAPI(
        title="yt-dlp Playground API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.include_router(api_router)

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _error_response(
            exc.status_code, exc.code, str(exc), exc.details, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = {
            "errors": [
                {"loc": [str(part) for part in error.get("loc", ())], "msg": error.get("msg", "")}
                for error in exc.errors()
            ]
        }
        return _error_response(400, "invalid_request", details=details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            message = "接口不存在"
        elif exc.status_code == 405:
            message = "请求方法不允许"
        else:
            message = None
        code = "invalid_request" if exc.status_code < 500 else "internal_error"
        return _error_response(exc.status_code, code, message, headers=dict(exc.headers or {}))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return _error_response(500, "internal_error")

    return app


app = create_app()
