"""The only module that executes SQL. Every function opens its own connection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.storage.db import connection

TERMINAL_STATUSES = ("completed", "failed", "canceled")


def _row(value: Any) -> dict[str, Any] | None:
    return dict(value) if value is not None else None


def get_job(db_path: Path, job_id: str) -> dict[str, Any] | None:
    with connection(db_path) as conn:
        return _row(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def list_jobs(db_path: Path, limit: int = 20) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def all_ids(db_path: Path) -> set[str]:
    with connection(db_path) as conn:
        return {row["id"] for row in conn.execute("SELECT id FROM jobs")}


def count_status(db_path: Path, status: str) -> int:
    with connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM jobs WHERE status = ?", (status,)).fetchone()
        return int(row["n"]) if row else 0


def create_job(
    db_path: Path,
    *,
    job_id: str,
    url: str,
    platform: str,
    quality: str,
    title: str | None,
    thumbnail_url: str | None,
    progress: dict[str, Any],
    created_at: str,
    expires_at: str,
) -> None:
    with connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, status, phase, url, platform, title, thumbnail_url, quality,
                progress_json, error_json, cancel_requested, output_filename,
                output_size_bytes, content_type, created_at, started_at, finished_at, expires_at
            ) VALUES (
                ?, 'queued', NULL, ?, ?, ?, ?, ?, ?, NULL, 0, NULL, NULL, NULL, ?, NULL, NULL, ?
            )
            """,
            (
                job_id,
                url,
                platform,
                title,
                thumbnail_url,
                quality,
                json.dumps(progress),
                created_at,
                expires_at,
            ),
        )


def mark_running(db_path: Path, job_id: str, started_at: str) -> bool:
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE jobs SET status = 'running', phase = 'downloading', started_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (started_at, job_id),
        )
        return cursor.rowcount == 1


def update_metadata(
    db_path: Path, job_id: str, title: str | None, thumbnail_url: str | None
) -> None:
    with connection(db_path) as conn:
        conn.execute(
            """
            UPDATE jobs
            SET title = COALESCE(?, title), thumbnail_url = COALESCE(?, thumbnail_url)
            WHERE id = ?
            """,
            (title, thumbnail_url, job_id),
        )


def update_progress(
    db_path: Path, job_id: str, progress: dict[str, Any], phase: str | None
) -> None:
    with connection(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET progress_json = ?, phase = ? WHERE id = ? AND status = 'running'",
            (json.dumps(progress), phase, job_id),
        )


def complete_job(
    db_path: Path,
    job_id: str,
    *,
    filename: str,
    size_bytes: int,
    content_type: str,
    finished_at: str,
    expires_at: str,
) -> bool:
    progress = {
        "percent": 100.0,
        "downloaded_bytes": size_bytes,
        "total_bytes": size_bytes,
        "speed_bps": None,
        "eta_seconds": None,
        "stage": None,
    }
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = 'completed', phase = NULL, progress_json = ?, output_filename = ?,
                output_size_bytes = ?, content_type = ?, finished_at = ?, expires_at = ?
            WHERE id = ? AND status = 'running'
            """,
            (
                json.dumps(progress),
                filename,
                size_bytes,
                content_type,
                finished_at,
                expires_at,
                job_id,
            ),
        )
        return cursor.rowcount == 1


def fail_job(
    db_path: Path,
    job_id: str,
    error: dict[str, Any],
    *,
    finished_at: str,
    expires_at: str,
) -> bool:
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = 'failed', phase = NULL, error_json = ?, finished_at = ?, expires_at = ?
            WHERE id = ? AND status IN ('queued', 'running')
            """,
            (json.dumps(error), finished_at, expires_at, job_id),
        )
        return cursor.rowcount == 1


def cancel_job(db_path: Path, job_id: str, *, finished_at: str, expires_at: str) -> bool:
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = 'canceled', phase = NULL, cancel_requested = 1,
                finished_at = ?, expires_at = ?
            WHERE id = ? AND status IN ('queued', 'running')
            """,
            (finished_at, expires_at, job_id),
        )
        return cursor.rowcount == 1


def cancel_queued(db_path: Path, job_id: str, *, finished_at: str, expires_at: str) -> bool:
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = 'canceled', phase = NULL, cancel_requested = 1,
                finished_at = ?, expires_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (finished_at, expires_at, job_id),
        )
        return cursor.rowcount == 1


def mark_cancel_requested(db_path: Path, job_id: str) -> None:
    with connection(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET cancel_requested = 1 WHERE id = ? AND status = 'running'",
            (job_id,),
        )


def delete_job(db_path: Path, job_id: str) -> bool:
    with connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return cursor.rowcount == 1


def delete_expired(db_path: Path, now_iso: str) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM jobs
            WHERE status IN ('completed', 'failed', 'canceled') AND expires_at <= ?
            """,
            (now_iso,),
        ).fetchall()
        expired = [dict(row) for row in rows]
        if expired:
            conn.executemany("DELETE FROM jobs WHERE id = ?", [(row["id"],) for row in expired])
        return expired


def recover_active(
    db_path: Path, error: dict[str, Any], *, finished_at: str, expires_at: str
) -> list[dict[str, Any]]:
    """Mark queued/running jobs as failed after a restart; return their rows."""
    with connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE status IN ('queued', 'running')").fetchall()
        active = [dict(row) for row in rows]
        if active:
            conn.executemany(
                """
                UPDATE jobs
                SET status = 'failed', phase = NULL, error_json = ?,
                    finished_at = ?, expires_at = ?
                WHERE id = ? AND status IN ('queued', 'running')
                """,
                [(json.dumps(error), finished_at, expires_at, row["id"]) for row in active],
            )
        return active
