"""Redis-backed durable job queue with expiring worker leases.

Queue messages contain only opaque job IDs. Request inputs live in the separate
expiring payload store. Workers must use the returned lease token for heartbeat,
acknowledgement, and retry so an expired worker cannot complete a newer lease.
"""
import math
import time
import uuid
from typing import Any


class RedisJobQueue:
    """Atomic pending/leased/dead-letter queue implemented with Redis Lua scripts."""

    _ENQUEUE = """
    -- atelier:enqueue
    if redis.call('EXISTS', KEYS[6]) == 1 then return 0 end
    if redis.call('ZSCORE', KEYS[1], ARGV[1]) then return 0 end
    if redis.call('ZSCORE', KEYS[2], ARGV[1]) then return 0 end
    if redis.call('ZSCORE', KEYS[5], ARGV[1]) then return 0 end
    redis.call('ZADD', KEYS[1], 'NX', tonumber(ARGV[2]), ARGV[1])
    return 1
    """

    _CLAIM = """
    -- atelier:claim
    local due = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', tonumber(ARGV[1]), 'LIMIT', 0, 1)
    if #due == 0 then return nil end
    local job_id = due[1]
    redis.call('ZREM', KEYS[1], job_id)
    local attempt = redis.call('HINCRBY', KEYS[4], job_id, 1)
    redis.call('HSET', KEYS[3], job_id, ARGV[2])
    redis.call('ZADD', KEYS[2], tonumber(ARGV[3]), job_id)
    return {job_id, tostring(attempt)}
    """

    _HEARTBEAT = """
    -- atelier:heartbeat
    if redis.call('HGET', KEYS[2], ARGV[1]) ~= ARGV[2] then return 0 end
    local expiry = redis.call('ZSCORE', KEYS[1], ARGV[1])
    if not expiry or tonumber(expiry) <= tonumber(ARGV[3]) then return 0 end
    redis.call('ZADD', KEYS[1], tonumber(ARGV[4]), ARGV[1])
    return 1
    """

    _ACK = """
    -- atelier:ack
    if redis.call('HGET', KEYS[3], ARGV[1]) ~= ARGV[2] then return 0 end
    local expiry = redis.call('ZSCORE', KEYS[2], ARGV[1])
    if not expiry or tonumber(expiry) <= tonumber(ARGV[4]) then return 0 end
    redis.call('ZREM', KEYS[2], ARGV[1])
    redis.call('HDEL', KEYS[3], ARGV[1])
    redis.call('HDEL', KEYS[4], ARGV[1])
    redis.call('SET', KEYS[1], '1', 'EX', tonumber(ARGV[3]))
    return 1
    """

    _RETRY = """
    -- atelier:retry
    if redis.call('HGET', KEYS[3], ARGV[1]) ~= ARGV[2] then return 0 end
    local expiry = redis.call('ZSCORE', KEYS[2], ARGV[1])
    if not expiry or tonumber(expiry) <= tonumber(ARGV[6]) then return 0 end
    redis.call('ZREM', KEYS[2], ARGV[1])
    redis.call('HDEL', KEYS[3], ARGV[1])
    local attempt = tonumber(redis.call('HGET', KEYS[4], ARGV[1]) or '0')
    redis.call('ZADD', KEYS[1], tonumber(ARGV[4]), ARGV[1])
    if attempt >= tonumber(ARGV[5]) then
        redis.call('ZREM', KEYS[1], ARGV[1])
        redis.call('ZADD', KEYS[5], tonumber(ARGV[4]), ARGV[1])
        return 2
    end
    return 1
    """

    _RECOVER = """
    -- atelier:recover
    local expired = redis.call(
        'ZRANGEBYSCORE', KEYS[2], '-inf', tonumber(ARGV[1]),
        'LIMIT', 0, tonumber(ARGV[4])
    )
    local recovered = 0
    for _, job_id in ipairs(expired) do
        redis.call('ZREM', KEYS[2], job_id)
        redis.call('HDEL', KEYS[3], job_id)
        local attempt = tonumber(redis.call('HGET', KEYS[4], job_id) or '0')
        if attempt >= tonumber(ARGV[3]) then
            redis.call('ZADD', KEYS[5], tonumber(ARGV[1]), job_id)
        else
            redis.call('ZADD', KEYS[1], tonumber(ARGV[2]), job_id)
        end
        recovered = recovered + 1
    end
    return recovered
    """

    _DISCARD_DEAD = """
    -- atelier:discard-dead
    local removed = redis.call('ZREM', KEYS[1], ARGV[1])
    redis.call('HDEL', KEYS[2], ARGV[1])
    return removed
    """

    def __init__(
        self,
        client: Any,
        *,
        namespace: str = "atelier:queue:v1",
        lease_seconds: int = 90,
        max_attempts: int = 3,
        completed_ttl_seconds: int = 86400,
        recovery_batch_size: int = 100,
    ):
        if not isinstance(namespace, str) or not namespace.strip() or namespace.endswith(":"):
            raise ValueError("namespace must be a non-empty string and must not end with ':'")
        for name, value in (
            ("lease_seconds", lease_seconds),
            ("max_attempts", max_attempts),
            ("completed_ttl_seconds", completed_ttl_seconds),
            ("recovery_batch_size", recovery_batch_size),
        ):
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        self.client = client
        self.namespace = namespace
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.completed_ttl_seconds = completed_ttl_seconds
        self.recovery_batch_size = recovery_batch_size
        self.pending_key = f"{namespace}:pending"
        self.leases_key = f"{namespace}:leases"
        self.tokens_key = f"{namespace}:lease-tokens"
        self.attempts_key = f"{namespace}:attempts"
        self.dead_key = f"{namespace}:dead"

    @staticmethod
    def _timestamp(value: float, name: str) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} must be a finite timestamp") from exc
        if not math.isfinite(result):
            raise ValueError(f"{name} must be a finite timestamp")
        return result

    @staticmethod
    def _job_id(job_id: str) -> str:
        if not isinstance(job_id, str) or not job_id or job_id.strip() != job_id:
            raise ValueError("job_id must be a non-empty string without surrounding whitespace")
        return job_id

    def _done_key(self, job_id: str) -> str:
        return f"{self.namespace}:done:{self._job_id(job_id)}"

    def enqueue(self, job_id: str, *, available_at: float = 0) -> bool:
        job_id = self._job_id(job_id)
        score = self._timestamp(available_at, "available_at")
        return bool(int(self.client.eval(
            self._ENQUEUE, 6, self.pending_key, self.leases_key,
            self.tokens_key, self.attempts_key, self.dead_key,
            self._done_key(job_id), job_id, score,
        )))

    def claim(self, *, now: float | None = None) -> dict[str, Any] | None:
        current = self._timestamp(time.time() if now is None else now, "now")
        token = uuid.uuid4().hex
        self.recover_expired(now=current)
        result = self.client.eval(
            self._CLAIM, 4, self.pending_key, self.leases_key,
            self.tokens_key, self.attempts_key, current, token,
            current + self.lease_seconds,
        )
        if not result:
            return None
        job_id, attempt = result
        if isinstance(job_id, bytes):
            job_id = job_id.decode("utf-8")
        if isinstance(attempt, bytes):
            attempt = attempt.decode("ascii")
        return {
            "job_id": self._job_id(job_id),
            "lease_token": token,
            "attempt": int(attempt),
            "lease_expires_at": current + self.lease_seconds,
        }

    def heartbeat(self, job_id: str, lease_token: str, *, now: float | None = None) -> bool:
        job_id = self._job_id(job_id)
        if not isinstance(lease_token, str) or not lease_token:
            raise ValueError("lease_token must be a non-empty string")
        current = self._timestamp(time.time() if now is None else now, "now")
        return bool(int(self.client.eval(
            self._HEARTBEAT, 2, self.leases_key, self.tokens_key,
            job_id, lease_token, current, current + self.lease_seconds,
        )))

    def acknowledge(self, job_id: str, lease_token: str, *, now: float | None = None) -> bool:
        job_id = self._job_id(job_id)
        current = self._timestamp(time.time() if now is None else now, "now")
        if not isinstance(lease_token, str) or not lease_token:
            raise ValueError("lease_token must be a non-empty string")
        return bool(int(self.client.eval(
            self._ACK, 4, self._done_key(job_id), self.leases_key,
            self.tokens_key, self.attempts_key, job_id, lease_token,
            self.completed_ttl_seconds, current,
        )))

    def retry(
        self, job_id: str, lease_token: str, *,
        available_at: float = 0, now: float | None = None,
    ) -> str | None:
        job_id = self._job_id(job_id)
        if not isinstance(lease_token, str) or not lease_token:
            raise ValueError("lease_token must be a non-empty string")
        score = self._timestamp(available_at, "available_at")
        result = int(self.client.eval(
            self._RETRY, 5, self.pending_key, self.leases_key,
            self.tokens_key, self.attempts_key, self.dead_key,
            job_id, lease_token, score, score, self.max_attempts,
            self._timestamp(time.time() if now is None else now, "now"),
        ))
        return {0: None, 1: "queued", 2: "dead"}.get(result)

    def recover_expired(self, *, now: float | None = None) -> int:
        current = self._timestamp(time.time() if now is None else now, "now")
        return int(self.client.eval(
            self._RECOVER, 5, self.pending_key, self.leases_key,
            self.tokens_key, self.attempts_key, self.dead_key,
            current, current, self.max_attempts, self.recovery_batch_size,
        ))

    def discard_dead(self, job_id: str) -> bool:
        job_id = self._job_id(job_id)
        return bool(int(self.client.eval(
            self._DISCARD_DEAD, 2, self.dead_key, self.attempts_key, job_id
        )))


    def pending_count(self) -> int:
        return int(self.client.zcard(self.pending_key))

    def leased_count(self) -> int:
        return int(self.client.zcard(self.leases_key))

    def dead_count(self) -> int:
        return int(self.client.zcard(self.dead_key))

    def dead_jobs(self, *, limit: int = 100) -> list[str]:
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        values = self.client.zrange(self.dead_key, 0, limit - 1)
        return [
            value.decode("utf-8") if isinstance(value, bytes) else value
            for value in values
        ]

    def ping(self) -> bool:
        return bool(self.client.ping())
