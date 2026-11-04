from __future__ import annotations

import secrets

from fastapi import Request, Response

from app.errors import ApiError


def require_token(request: Request) -> None:
    """Optional shared secret between the Pages Function and the API.

    Empty YTP_API_TOKEN disables the check (local development).
    """
    expected = request.app.state.settings.api_token
    if not expected:
        return
    provided = request.headers.get("x-api-token", "")
    if not provided or not secrets.compare_digest(provided, expected):
        raise ApiError(401, "unauthorized")


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
