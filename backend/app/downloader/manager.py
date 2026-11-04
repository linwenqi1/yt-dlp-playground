"""In-process job queue, worker threads, cancellation, recovery and TTL cleanup."""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any

from app.config import Settings
from app.core import timeutil
from app.downloader.base import Downloader, DownloadRequest, JobCancelled, ProgressUpdate
from app.errors import ApiError, error_detail
from app.storage import files, jobs_repo
from app.storage.db import init_db

logger = logging.getLogger(__name__)

SWEEP_INTERVAL_SECONDS = 600
PROGRESS_WRITE_INTERVAL_SECONDS = 1.0


class JobManager:
    def __init__(self, settings: Settings, downloader: Downloader) -> None:
        self.settings = settings
        self.downloader = downloader
        self.queue: queue.Queue[str | None] = queue.Queue(maxsize=settings.max_queued_jobs)
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._workers: list[threading.Thread] = []

    @property
    def db_path(self):
        return self.settings.db_path

    def start(self) -> None:
        self.settings.ensure_dirs()
        init_db(self.settings.db_path)
        self._recover()
        self.sweep_expired()
        for index in range(self.settings.max_concurrent_jobs):
            thread = threading.Thread(
                target=self._worker_loop, name=f"ytp-worker-{index}", daemon=True
            )
            thread.start()
            self._workers.append(thread)
        threading.Thread(target=self._sweeper_loop, name="ytp-sweeper", daemon=True).start()
        logger.info(
            "job manager started: workers=%s queue_max=%s data_dir=%s",
            self.settings.max_concurrent_jobs,
            self.settings.max_queued_jobs,
            self.settings.data_dir,
        )

    def stop(self) -> None:
        self._stop.set()
        for _ in self._workers:
            try:
                self.queue.put_nowait(None)
            except queue.Full:
                break
        for thread in self._workers:
            thread.join(timeout=2)

    def submit(self, job_id: str) -> None:
        """Queue a job; raises queue.Full when the bounded queue is saturated."""
        self.queue.put_nowait(job_id)

    @property
    def queue_depth(self) -> int:
        return self.queue.qsize()

    @property
    def active_count(self) -> int:
        return jobs_repo.count_status(self.db_path, "running")

    def request_cancel(self, job_id: str) -> dict[str, Any]:
        row = jobs_repo.get_job(self.db_path, job_id)
        if row is None:
            raise ApiError(404, "job_not_found")
        if row["status"] == "canceled":
            return row
        if row["status"] in ("completed", "failed"):
            raise ApiError(409, "job_not_cancellable")

        finished_at, expires_at = self._terminal_times()
        if jobs_repo.cancel_queued(
            self.db_path, job_id, finished_at=finished_at, expires_at=expires_at
        ):
            return jobs_repo.get_job(self.db_path, job_id) or row

        jobs_repo.mark_cancel_requested(self.db_path, job_id)
        with self._lock:
            event = self._cancel_events.get(job_id)
        if event is not None:
            event.set()

        fresh = jobs_repo.get_job(self.db_path, job_id)
        if fresh is None:
            raise ApiError(404, "job_not_found")
        if fresh["status"] in ("completed", "failed"):
            raise ApiError(409, "job_not_cancellable")
        return fresh

    def sweep_expired(self) -> int:
        rows = jobs_repo.delete_expired(self.db_path, timeutil.iso())
        for row in rows:
            files.remove_job_dir(files.job_dir(self.settings, row["id"]))
        if rows:
            logger.info("removed %s expired job(s)", len(rows))
        return len(rows)

    def _recover(self) -> None:
        finished_at, expires_at = self._terminal_times()
        rows = jobs_repo.recover_active(
            self.db_path,
            error_detail("interrupted"),
            finished_at=finished_at,
            expires_at=expires_at,
        )
        for row in rows:
            files.remove_job_dir(files.job_dir(self.settings, row["id"]))
        if rows:
            logger.warning("marked %s interrupted job(s) as failed", len(rows))
        known = jobs_repo.all_ids(self.db_path)
        removed = files.cleanup_orphans(self.settings.jobs_dir, known)
        if removed:
            logger.info("removed %s orphan job directorie(s)", removed)

    def _terminal_times(self) -> tuple[str, str]:
        moment = timeutil.now()
        return (
            timeutil.iso(moment),
            timeutil.iso(timeutil.plus_hours(moment, self.settings.job_ttl_hours)),
        )

    def _sweeper_loop(self) -> None:
        while not self._stop.wait(SWEEP_INTERVAL_SECONDS):
            try:
                self.sweep_expired()
            except Exception:  # noqa: BLE001 - the sweeper must never die
                logger.exception("expired job sweep failed")

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if job_id is not None:
                    self._run(job_id)
            except Exception:  # noqa: BLE001 - a worker must survive any job failure
                logger.exception("unexpected worker failure for job %s", job_id)
            finally:
                self.queue.task_done()

    def _run(self, job_id: str) -> None:
        row = jobs_repo.get_job(self.db_path, job_id)
        if row is None or row["status"] != "queued":
            return

        job_dir = files.job_dir(self.settings, job_id)
        try:
            files.prepare_job_dir(job_dir)
        except OSError:
            logger.exception("cannot create job directory for %s", job_id)
            finished_at, expires_at = self._terminal_times()
            jobs_repo.fail_job(
                self.db_path,
                job_id,
                error_detail("internal_error"),
                finished_at=finished_at,
                expires_at=expires_at,
            )
            return

        if not jobs_repo.mark_running(self.db_path, job_id, timeutil.iso()):
            files.remove_job_dir(job_dir)
            return

        cancel_event = threading.Event()
        with self._lock:
            self._cancel_events[job_id] = cancel_event

        last_write = 0.0

        def on_progress(update: ProgressUpdate) -> None:
            nonlocal last_write
            now = time.monotonic()
            is_phase_change = update.phase == "postprocessing" or update.percent is None
            if not is_phase_change and now - last_write < PROGRESS_WRITE_INTERVAL_SECONDS:
                return
            last_write = now
            try:
                jobs_repo.update_progress(self.db_path, job_id, update.as_dict(), update.phase)
            except Exception:  # noqa: BLE001 - progress is best effort
                logger.exception("failed to persist progress for job %s", job_id)

        def on_metadata(title: str | None, thumbnail_url: str | None) -> None:
            try:
                jobs_repo.update_metadata(self.db_path, job_id, title, thumbnail_url)
            except Exception:  # noqa: BLE001
                logger.exception("failed to persist metadata for job %s", job_id)

        request = DownloadRequest(
            job_id=job_id,
            url=row["url"],
            quality=row["quality"],
            job_dir=job_dir,
            cancel_event=cancel_event,
            on_progress=on_progress,
            on_metadata=on_metadata,
        )

        try:
            result = self.downloader.download(request)
            fresh = jobs_repo.get_job(self.db_path, job_id)
            if cancel_event.is_set() or (fresh is not None and fresh["cancel_requested"]):
                files.remove_job_dir(job_dir)
                self._finish_canceled(job_id)
                return

            finished_at, expires_at = self._terminal_times()
            title = result.title or (fresh or row).get("title")
            size = result.path.stat().st_size
            completed = jobs_repo.complete_job(
                self.db_path,
                job_id,
                filename=files.display_filename(title, result.path.suffix),
                size_bytes=size,
                content_type=files.content_type_for(result.path),
                finished_at=finished_at,
                expires_at=expires_at,
            )
            if not completed:
                files.remove_job_dir(job_dir)
        except JobCancelled as exc:
            files.remove_job_dir(job_dir)
            finished_at, expires_at = self._terminal_times()
            if exc.reason == "timeout":
                logger.warning("job %s timed out", job_id)
                jobs_repo.fail_job(
                    self.db_path,
                    job_id,
                    error_detail("timeout"),
                    finished_at=finished_at,
                    expires_at=expires_at,
                )
            else:
                jobs_repo.cancel_job(
                    self.db_path, job_id, finished_at=finished_at, expires_at=expires_at
                )
        except ApiError as exc:
            files.remove_job_dir(job_dir)
            finished_at, expires_at = self._terminal_times()
            logger.warning("job %s failed: %s", job_id, exc.code)
            jobs_repo.fail_job(
                self.db_path,
                job_id,
                exc.to_detail(),
                finished_at=finished_at,
                expires_at=expires_at,
            )
        except Exception:  # noqa: BLE001 - never leak internals to clients
            files.remove_job_dir(job_dir)
            finished_at, expires_at = self._terminal_times()
            logger.exception("job %s crashed", job_id)
            jobs_repo.fail_job(
                self.db_path,
                job_id,
                error_detail("internal_error"),
                finished_at=finished_at,
                expires_at=expires_at,
            )
        finally:
            with self._lock:
                self._cancel_events.pop(job_id, None)

    def _finish_canceled(self, job_id: str) -> None:
        finished_at, expires_at = self._terminal_times()
        jobs_repo.cancel_job(self.db_path, job_id, finished_at=finished_at, expires_at=expires_at)
