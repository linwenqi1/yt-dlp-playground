"""UTC timestamp helpers. API timestamps are RFC 3339 strings ending in Z."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None = None) -> str:
    moment = value or now()
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def plus_hours(value: datetime, hours: int | float) -> datetime:
    return value + timedelta(hours=hours)
