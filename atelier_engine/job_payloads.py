"""Safe, expiring storage for durable background-job input payloads.

Large or sensitive request inputs (including reference-image bytes) stay out of
job-status records and queue messages. Queue messages should carry only a job
identifier; workers retrieve the validated payload from this store.
"""
import base64
import json
import math
from typing import Any


class RedisJobPayloadStore:
    """Store JSON-encoded, type-preserving job inputs under expiring Redis keys."""

    def __init__(
        self,
        client: Any,
        *,
        namespace: str = "atelier:job-payloads:v1",
        ttl_seconds: int = 86400,
        max_payload_bytes: int = 15 * 1024 * 1024,
    ):
        if not isinstance(namespace, str) or not namespace.strip() or namespace.endswith(":"):
            raise ValueError("namespace must be a non-empty string and must not end with ':'")
        if type(ttl_seconds) is not int or ttl_seconds < 1:
            raise ValueError("ttl_seconds must be a positive integer")
        if type(max_payload_bytes) is not int or max_payload_bytes < 1:
            raise ValueError("max_payload_bytes must be a positive integer")
        self.client = client
        self.namespace = namespace
        self.ttl_seconds = ttl_seconds
        self.max_payload_bytes = max_payload_bytes

    def _key(self, job_id: str) -> str:
        if not isinstance(job_id, str) or not job_id or job_id.strip() != job_id:
            raise ValueError("job_id must be a non-empty string without surrounding whitespace")
        return f"{self.namespace}:{job_id}"

    @classmethod
    def _pack(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("job payload numbers must be finite")
            return value
        if isinstance(value, bytes):
            return {"$atelier_type": "bytes", "base64": base64.b64encode(value).decode("ascii")}
        if isinstance(value, tuple):
            return {"$atelier_type": "tuple", "items": [cls._pack(item) for item in value]}
        if isinstance(value, list):
            return [cls._pack(item) for item in value]
        if isinstance(value, dict):
            if not all(isinstance(key, str) for key in value):
                raise ValueError("job payload dictionary keys must be strings")
            return {
                "$atelier_type": "dict",
                "items": [[key, cls._pack(item)] for key, item in value.items()],
            }
        raise ValueError(f"unsupported job payload value: {type(value).__name__}")

    @classmethod
    def _unpack(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [cls._unpack(item) for item in value]
        if isinstance(value, dict):
            kind = value.get("$atelier_type")
            if kind == "bytes" and set(value) == {"$atelier_type", "base64"}:
                try:
                    return base64.b64decode(value["base64"], validate=True)
                except (TypeError, ValueError) as exc:
                    raise ValueError("stored job payload contains invalid binary data") from exc
            if kind == "tuple" and set(value) == {"$atelier_type", "items"}:
                return tuple(cls._unpack(item) for item in value["items"])
            if kind == "dict" and set(value) == {"$atelier_type", "items"}:
                items = value["items"]
                if not isinstance(items, list):
                    raise ValueError("stored job payload contains an invalid dictionary")
                result = {}
                for pair in items:
                    if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
                        raise ValueError("stored job payload contains an invalid dictionary entry")
                    if pair[0] in result:
                        raise ValueError("stored job payload contains duplicate dictionary keys")
                    result[pair[0]] = cls._unpack(pair[1])
                return result
            raise ValueError("stored job payload contains an unknown encoded object")
        return value

    def save(self, job_id: str, payload: Any) -> bool:
        packed = self._pack(payload)
        encoded = json.dumps(packed, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > self.max_payload_bytes:
            raise ValueError("job payload exceeds the configured storage limit")
        result = self.client.set(
            self._key(job_id), encoded, ex=self.ttl_seconds, nx=True
        )
        return bool(result)

    def load(self, job_id: str) -> Any:
        raw = self.client.get(self._key(job_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return self._unpack(json.loads(raw))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("stored job payload is not valid JSON") from exc

    def delete(self, job_id: str) -> bool:
        return bool(self.client.delete(self._key(job_id)))
