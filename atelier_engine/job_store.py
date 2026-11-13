"""Job storage contracts and the thread-safe in-memory implementation.

The in-memory adapter is intended for tests and single-process development.
It is not a cross-process store and must not be used to justify multi-worker
deployment.
"""
from copy import deepcopy
import math
from threading import RLock
from typing import Any, Protocol


class JobStore(Protocol):
    """Operations required by HTTP routes and background job workers."""

    def create(self, job_id: str, record: dict[str, Any]) -> bool:
        """Create a job if its identifier does not already exist."""

    def update_running(self, job_id: str, fields: dict[str, Any], finished_at: float) -> bool:
        """Update a running job, stamping terminal completion exactly once."""

    def update_running_with_lease(
        self, job_id: str, fields: dict[str, Any], finished_at: float,
        *, queue: Any, lease_token: str,
    ) -> bool:
        """Atomically fence a job update against the current Redis queue lease."""

    def snapshot(self, job_id: str) -> dict[str, Any] | None:
        """Return an isolated copy of a job record."""

    def access_token(self, job_id: str) -> str | None:
        """Return the private access token for internal response construction."""

    def delete(self, job_id: str) -> bool:
        """Delete a job record."""

    def active_count(self) -> int:
        """Return the number of jobs currently in the running state."""

    def touch_running(self, job_id: str, now: float) -> bool:
        """Refresh the liveness timestamp of a running job."""

    def maintain(
        self, *, now: float, max_runtime_seconds: int,
        finished_ttl_seconds: int, max_records: int,
    ) -> None:
        """Expire abandoned jobs and prune old terminal history."""


class InMemoryJobStore:
    """Thread-safe adapter preserving isolated snapshots and terminal-state rules."""

    def __init__(self, records: dict[str, dict[str, Any]] | None = None):
        self._records = records if records is not None else {}
        self._lock = RLock()

    @property
    def records(self) -> dict[str, dict[str, Any]]:
        """Expose backing records for legacy single-process compatibility only."""
        return self._records

    @property
    def lock(self) -> RLock:
        """Expose the lock for legacy maintenance code during migration."""
        return self._lock

    def create(self, job_id: str, record: dict[str, Any]) -> bool:
        with self._lock:
            if job_id in self._records:
                return False
            self._records[job_id] = deepcopy(record)
            return True

    def update_running(self, job_id: str, fields: dict[str, Any], finished_at: float) -> bool:
        with self._lock:
            current = self._records.get(job_id)
            if current is None or current.get("status") != "running":
                return False
            was_running = current.get("status") == "running"
            current.update(deepcopy(fields))
            if was_running and current.get("status") != "running":
                current["finished_at"] = finished_at
            return True

    def snapshot(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            current = self._records.get(job_id)
            return deepcopy(current) if current is not None else None

    def access_token(self, job_id: str) -> str | None:
        with self._lock:
            record = self._records.get(job_id)
            return record.get("access_token") if record else None

    def delete(self, job_id: str) -> bool:
        with self._lock:
            return self._records.pop(job_id, None) is not None

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for record in self._records.values()
                       if record.get("status") == "running")

    def touch_running(self, job_id: str, now: float) -> bool:
        with self._lock:
            record = self._records.get(job_id)
            if record is None or record.get("status") != "running":
                return False
            record["last_activity_at"] = now
            return True

    def maintain(
        self, *, now: float, max_runtime_seconds: int,
        finished_ttl_seconds: int, max_records: int,
    ) -> None:
        with self._lock:
            for job_id, record in list(self._records.items()):
                created = record.get("last_activity_at", record.get("created", now))
                if (record.get("status") == "running"
                        and now - created >= max_runtime_seconds):
                    record.update({
                        "status": "error", "step": "",
                        "error": "This job took too long and was stopped. Please retry.",
                        "finished_at": now,
                    })
                elif record.get("status") != "running":
                    finished_at = record.get("finished_at") or created
                    if now - finished_at >= finished_ttl_seconds:
                        del self._records[job_id]
            if len(self._records) > max_records:
                finished = sorted(
                    ((record.get("finished_at") or record.get("created", now), job_id)
                     for job_id, record in self._records.items()
                     if record.get("status") != "running"),
                )
                for _, job_id in finished[:len(self._records) - max_records]:
                    self._records.pop(job_id, None)


class RedisJobStore:
    """Redis-backed job records with atomic global capacity reservation.

    The adapter is selected only when JOB_QUEUE_ENABLED explicitly opts the
    Flask app into Redis-backed records and the durable queue. The default
    remains the in-memory single-process development adapter.
    """

    _CREATE_SCRIPT = """
    if redis.call('EXISTS', KEYS[1]) == 1 then return -1 end
    local active = redis.call('ZCARD', KEYS[2])
    if active >= tonumber(ARGV[1]) then return 0 end
    redis.call('SET', KEYS[1], ARGV[2])
    redis.call('ZADD', KEYS[2], tonumber(ARGV[4]), ARGV[5])
    return 1
    """

    _UPDATE_SCRIPT = """
    local raw = redis.call('GET', KEYS[1])
    if not raw then return 0 end
    local record = cjson.decode(raw)
    if record['status'] ~= 'running' then return 0 end
    local fields = cjson.decode(ARGV[1])
    for key, value in pairs(fields) do record[key] = value end
    if fields['status'] and fields['status'] ~= 'running' then
        record['finished_at'] = tonumber(ARGV[2])
        redis.call('ZREM', KEYS[2], ARGV[3])
        redis.call('ZADD', KEYS[3], tonumber(record['finished_at']), ARGV[3])
    end
    if record['status'] == 'running' then
        redis.call('SET', KEYS[1], cjson.encode(record))
    else
        redis.call('SET', KEYS[1], cjson.encode(record), 'EX', tonumber(ARGV[4]))
    end
    return 1
    """

    _FENCED_UPDATE_SCRIPT = """
    -- atelier:fenced-update
    if redis.call('HGET', KEYS[4], ARGV[3]) ~= ARGV[5] then return 0 end
    local lease_expiry = redis.call('ZSCORE', KEYS[5], ARGV[3])
    if not lease_expiry or tonumber(lease_expiry) <= tonumber(ARGV[2]) then return 0 end
    local raw = redis.call('GET', KEYS[1])
    if not raw then return 0 end
    local record = cjson.decode(raw)
    if record['status'] ~= 'running' then return 0 end
    local fields = cjson.decode(ARGV[1])
    for key, value in pairs(fields) do record[key] = value end
    if fields['status'] and fields['status'] ~= 'running' then
        record['finished_at'] = tonumber(ARGV[2])
        redis.call('ZREM', KEYS[2], ARGV[3])
        redis.call('ZADD', KEYS[3], tonumber(record['finished_at']), ARGV[3])
        redis.call('SET', KEYS[1], cjson.encode(record), 'EX', tonumber(ARGV[4]))
    else
        redis.call('ZADD', KEYS[2], tonumber(ARGV[2]), ARGV[3])
        redis.call('SET', KEYS[1], cjson.encode(record))
    end
    redis.call('ZADD', KEYS[5], tonumber(ARGV[2]) + tonumber(ARGV[6]), ARGV[3])
    return 1
    """

    _DELETE_SCRIPT = """
    local removed = redis.call('DEL', KEYS[1])
    redis.call('ZREM', KEYS[2], ARGV[1])
    redis.call('ZREM', KEYS[3], ARGV[1])
    return removed
    """

    def __init__(
        self,
        client: Any,
        *,
        namespace: str = "atelier:jobs:v1",
        max_active: int = 20,
        record_ttl_seconds: int = 86400,
    ):
        if not isinstance(namespace, str) or not namespace.strip() or namespace.endswith(":"):
            raise ValueError("namespace must be a non-empty string and must not end with ':'")
        if type(max_active) is not int or max_active < 1:
            raise ValueError("max_active must be a positive integer")
        if type(record_ttl_seconds) is not int or record_ttl_seconds < 1:
            raise ValueError("record_ttl_seconds must be a positive integer")
        self.client = client
        self.namespace = namespace
        self.max_active = max_active
        self.record_ttl_seconds = record_ttl_seconds
        self.active_key = f"{namespace}:active"
        self.finished_key = f"{namespace}:finished"

    def _key(self, job_id: str) -> str:
        if not isinstance(job_id, str) or not job_id or job_id.strip() != job_id:
            raise ValueError("job_id must be a non-empty string without surrounding whitespace")
        return f"{self.namespace}:{job_id}"

    @staticmethod
    def _encode(record: dict[str, Any]) -> str:
        import json
        try:
            return json.dumps(record, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("job records must contain finite JSON-compatible values") from exc

    def create(self, job_id: str, record: dict[str, Any]) -> bool:
        import time
        if not isinstance(record, dict):
            raise ValueError("job record must be a dictionary")
        if record.get("status") != "running":
            raise ValueError("new jobs must start in running state")
        payload = self._encode(record)
        created_at = record.get("created_at", record.get("created"))
        try:
            score = float(time.time() if created_at is None else created_at)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("created timestamp must be finite") from exc
        if not math.isfinite(score):
            raise ValueError("created timestamp must be finite")
        finished_at = record.get("finished_at")
        if finished_at is not None:
            try:
                finished_at = float(finished_at)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("finished_at must be a finite timestamp") from exc
            if not math.isfinite(finished_at):
                raise ValueError("finished_at must be a finite timestamp")
        result = self.client.eval(
            self._CREATE_SCRIPT, 2, self._key(job_id), self.active_key,
            self.max_active, payload, self.record_ttl_seconds, score, job_id,
        )
        return int(result) == 1

    def update_running(self, job_id: str, fields: dict[str, Any], finished_at: float) -> bool:
        if not isinstance(fields, dict):
            raise ValueError("job update fields must be a dictionary")
        encoded = self._encode(fields)
        try:
            finished_at = float(finished_at)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("finished_at must be a finite timestamp") from exc
        if not math.isfinite(finished_at):
            raise ValueError("finished_at must be a finite timestamp")
        if "status" in fields and (
            not isinstance(fields["status"], str) or not fields["status"].strip()
        ):
            raise ValueError("job status must be a non-empty string")
        result = self.client.eval(
            self._UPDATE_SCRIPT, 3, self._key(job_id), self.active_key,
            self.finished_key, encoded, finished_at, job_id, self.record_ttl_seconds,
        )
        return bool(int(result))

    def update_running_with_lease(
        self, job_id: str, fields: dict[str, Any], finished_at: float,
        *, queue: Any, lease_token: str,
    ) -> bool:
        """Atomically fence a job update against the current Redis queue lease."""
        if not isinstance(fields, dict):
            raise ValueError("job update fields must be a dictionary")
        encoded = self._encode(fields)
        try:
            timestamp = float(finished_at)
            lease_seconds = queue.lease_seconds
        except (TypeError, ValueError, OverflowError, AttributeError) as exc:
            raise ValueError("a valid queue lease and finite timestamp are required") from exc
        if not math.isfinite(timestamp):
            raise ValueError("finished_at must be a finite timestamp")
        if type(lease_seconds) is not int or lease_seconds < 1:
            raise ValueError("queue lease_seconds must be a positive integer")
        if not isinstance(lease_token, str) or not lease_token:
            raise ValueError("lease_token must be a non-empty string")
        if "status" in fields and (
            not isinstance(fields["status"], str) or not fields["status"].strip()
        ):
            raise ValueError("job status must be a non-empty string")
        result = self.client.eval(
            self._FENCED_UPDATE_SCRIPT, 5, self._key(job_id),
            self.active_key, self.finished_key, queue.tokens_key, queue.leases_key,
            encoded, timestamp, job_id, self.record_ttl_seconds,
            lease_token, lease_seconds,
        )
        return bool(int(result))

    def snapshot(self, job_id: str) -> dict[str, Any] | None:
        import json
        raw = self.client.get(self._key(job_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("stored job record must be a JSON object")
        return value

    def access_token(self, job_id: str) -> str | None:
        record = self.snapshot(job_id)
        token = record.get("access_token") if record else None
        return token if isinstance(token, str) else None

    def delete(self, job_id: str) -> bool:
        result = self.client.eval(
            self._DELETE_SCRIPT, 3, self._key(job_id), self.active_key,
            self.finished_key, job_id
        )
        return bool(int(result))

    _TOUCH_SCRIPT = """
    -- atelier:touch
    local raw = redis.call('GET', KEYS[1])
    if not raw then return 0 end
    local record = cjson.decode(raw)
    if record['status'] ~= 'running' then return 0 end
    redis.call('ZADD', KEYS[2], tonumber(ARGV[1]), ARGV[2])
    return 1
    """

    def active_count(self) -> int:
        """Return the globally reserved running-job count."""
        return int(self.client.zcard(self.active_key))

    def touch_running(self, job_id: str, now: float) -> bool:
        try:
            timestamp = float(now)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("now must be a finite timestamp") from exc
        if not math.isfinite(timestamp):
            raise ValueError("now must be a finite timestamp")
        return bool(int(self.client.eval(
            self._TOUCH_SCRIPT, 2, self._key(job_id), self.active_key,
            timestamp, job_id,
        )))

    def maintain(
        self, *, now: float, max_runtime_seconds: int,
        finished_ttl_seconds: int, max_records: int,
    ) -> None:
        """Expire stale running jobs and prune terminal history using indexes."""
        stale_ids = self.client.zrangebyscore(
            self.active_key, "-inf", now - max_runtime_seconds
        )
        for raw_job_id in stale_ids:
            job_id = raw_job_id.decode("utf-8") if isinstance(raw_job_id, bytes) else raw_job_id
            record = self.snapshot(job_id)
            if record is None or record.get("status") != "running":
                self.client.zrem(self.active_key, job_id)
                continue
            self.update_running(
                job_id,
                {"status": "error", "step": "",
                 "error": "This job took too long and was stopped. Please retry."},
                finished_at=now,
            )

        finished_ids = self.client.zrange(self.finished_key, 0, -1)
        live_finished = []
        for raw_job_id in finished_ids:
            job_id = raw_job_id.decode("utf-8") if isinstance(raw_job_id, bytes) else raw_job_id
            record = self.snapshot(job_id)
            if record is None:
                self.client.zrem(self.finished_key, job_id)
                continue
            created = record.get("created", record.get("created_at", now))
            finished_at = record.get("finished_at") or created
            if now - finished_at >= finished_ttl_seconds:
                self.delete(job_id)
            else:
                live_finished.append(job_id)

        # Running jobs are governed by queue leases and are never pruned here.
        max_finished = max(0, max_records - self.active_count())
        excess = max(0, len(live_finished) - max_finished)
        for job_id in live_finished[:excess]:
            self.delete(job_id)

    def ping(self) -> bool:
        """Validate Redis connectivity; propagate connection errors to callers."""
        return bool(self.client.ping())
