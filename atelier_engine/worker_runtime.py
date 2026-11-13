"""Supervised worker runtime for the Redis lease queue.

This module is deliberately independent of Flask. A worker process supplies a
small allowlisted handler registry; the queue carries only job IDs and handlers
load their serialized inputs from the expiring payload store.
"""
from contextvars import ContextVar
import math
import logging
import threading
import time
from typing import Any, Callable


current_worker_lease: ContextVar[tuple[str, str] | None] = ContextVar(
    "atelier_current_worker_lease", default=None
)


class RedisJobWorker:
    """Execute allowlisted handlers with heartbeats, fencing, and retry handling."""

    def __init__(
        self,
        queue: Any,
        payload_store: Any,
        job_store: Any,
        handlers: dict[str, Callable[..., Any]],
        *,
        heartbeat_interval_seconds: float | None = None,
        retry_backoff_seconds: int = 5,
        poll_interval_seconds: float = 1,
        logger: logging.Logger | None = None,
    ):
        self.queue = queue
        self.payload_store = payload_store
        self.job_store = job_store
        self.handlers = dict(handlers)
        lease_seconds = getattr(queue, "lease_seconds", 90)
        self.heartbeat_interval_seconds = (
            heartbeat_interval_seconds
            if heartbeat_interval_seconds is not None
            else max(0.05, lease_seconds / 3)
        )
        if (not math.isfinite(self.heartbeat_interval_seconds)
                or self.heartbeat_interval_seconds <= 0):
            raise ValueError("heartbeat_interval_seconds must be a positive finite number")
        if self.heartbeat_interval_seconds >= lease_seconds / 2:
            raise ValueError("heartbeat_interval_seconds must be less than half the queue lease")
        if type(retry_backoff_seconds) is not int or retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be a non-negative integer")
        if not math.isfinite(poll_interval_seconds) or poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be a positive finite number")
        self.retry_backoff_seconds = retry_backoff_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.logger = logger or logging.getLogger("atelier.worker")
        self._stopping = threading.Event()

    def _update_if_owned(self, job_id: str, token: str, fields: dict[str, Any]) -> bool:
        now = time.time()
        if hasattr(self.job_store, "update_running_with_lease"):
            return bool(self.job_store.update_running_with_lease(
                job_id, fields, now, queue=self.queue, lease_token=token
            ))
        if not self.queue.heartbeat(job_id, token):
            return False
        if (hasattr(self.job_store, "touch_running")
                and not self.job_store.touch_running(job_id, now)):
            return False
        return bool(self.job_store.update_running(job_id, fields, finished_at=now))

    def _mark_terminal_error(self, job_id: str, token: str, message: str) -> bool:
        return self._update_if_owned(job_id, token, {
            "status": "error", "step": "", "error": message,
        })

    def _finalize_dead_letters(self):
        if not hasattr(self.queue, "dead_jobs"):
            return
        self.queue.recover_expired()
        for job_id in self.queue.dead_jobs(limit=100):
            record = self.job_store.snapshot(job_id)
            if record is not None and record.get("status") == "running":
                self.job_store.update_running(
                    job_id,
                    {"status": "error", "step": "",
                     "error": "Background processing stopped after repeated worker failures. Please retry."},
                    finished_at=time.time(),
                )
            self.payload_store.delete(job_id)
            self.queue.discard_dead(job_id)

    def run_once(self) -> bool:
        """Claim and process at most one due job. Return False when queue is empty."""
        self._finalize_dead_letters()
        claim = self.queue.claim()
        if claim is None:
            return False
        job_id = claim["job_id"]
        token = claim["lease_token"]
        attempt = claim["attempt"]
        heartbeat_lost = threading.Event()
        heartbeat_stop = threading.Event()

        def heartbeat_loop():
            while not heartbeat_stop.wait(self.heartbeat_interval_seconds):
                try:
                    if not self.queue.heartbeat(job_id, token):
                        heartbeat_lost.set()
                        return
                    if (hasattr(self.job_store, "touch_running")
                            and not self.job_store.touch_running(job_id, time.time())):
                        snapshot = self.job_store.snapshot(job_id)
                        if snapshot is not None and snapshot.get("status") != "running":
                            heartbeat_stop.set()
                            return
                        heartbeat_lost.set()
                        return
                except Exception:
                    self.logger.exception("Worker heartbeat failed for job %s", job_id)
                    heartbeat_lost.set()
                    return

        heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            name=f"atelier-heartbeat-{job_id[:8]}",
            daemon=True,
        )
        lease_context = current_worker_lease.set((job_id, token))
        heartbeat_started = False
        try:
            heartbeat_thread.start()
            heartbeat_started = True
            existing = self.job_store.snapshot(job_id)
            if existing is None or existing.get("status") != "running":
                if self.queue.acknowledge(job_id, token):
                    self.payload_store.delete(job_id)
                return True

            try:
                payload = self.payload_store.load(job_id)
            except Exception:
                self.logger.exception("Could not load saved input for job %s", job_id)
                if self._mark_terminal_error(
                    job_id, token,
                    "The saved job input could not be read. Please submit the request again.",
                ) and self.queue.acknowledge(job_id, token):
                    self.payload_store.delete(job_id)
                return True
            if not isinstance(payload, dict):
                if not self._mark_terminal_error(
                    job_id, token, "The saved job input is missing or invalid. Please retry."
                ):
                    heartbeat_lost.set()
                if not heartbeat_lost.is_set() and self.queue.acknowledge(job_id, token):
                    self.payload_store.delete(job_id)
                return True

            handler_name = payload.get("handler")
            args = payload.get("args")
            handler = self.handlers.get(handler_name) if isinstance(handler_name, str) else None
            if handler is None or not isinstance(args, (list, tuple)):
                if not self._mark_terminal_error(
                    job_id, token, "This background job type is not available. Please retry."
                ):
                    heartbeat_lost.set()
                if not heartbeat_lost.is_set() and self.queue.acknowledge(job_id, token):
                    self.payload_store.delete(job_id)
                return True

            try:
                handler(*args)
            except Exception:
                self.logger.exception("Background job %s failed unexpectedly", job_id)
                if heartbeat_lost.is_set():
                    return True
                max_attempts = getattr(self.queue, "max_attempts", None)
                if isinstance(max_attempts, int) and attempt >= max_attempts:
                    if not self._mark_terminal_error(
                        job_id, token,
                        "Background processing failed after repeated attempts. Please retry.",
                    ):
                        heartbeat_lost.set()
                        return True
                delay = self.retry_backoff_seconds * (2 ** max(0, attempt - 1))
                outcome = self.queue.retry(
                    job_id, token, available_at=time.time() + delay
                )
                if outcome == "dead":
                    self.payload_store.delete(job_id)
                return True

            if heartbeat_lost.is_set():
                return True
            snapshot = self.job_store.snapshot(job_id)
            if snapshot is not None and snapshot.get("status") == "running":
                if not self._mark_terminal_error(
                    job_id, token,
                    "The worker finished without recording a terminal result. Please retry.",
                ):
                    heartbeat_lost.set()
            if not heartbeat_lost.is_set() and self.queue.acknowledge(job_id, token):
                self.payload_store.delete(job_id)
            return True
        finally:
            heartbeat_stop.set()
            if heartbeat_started:
                heartbeat_thread.join(timeout=max(1, self.heartbeat_interval_seconds * 2))
            current_worker_lease.reset(lease_context)

    def run_forever(self):
        """Poll continuously until stop() is called."""
        self._stopping.clear()
        while not self._stopping.is_set():
            try:
                claimed = self.run_once()
            except Exception:
                self.logger.exception("Worker loop failed")
                claimed = False
            if not claimed:
                self._stopping.wait(self.poll_interval_seconds)

    def stop(self):
        self._stopping.set()
