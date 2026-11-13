"""Contract and Redis integration tests for durable job input payloads."""
import os
import unittest
import uuid

from atelier_engine.job_payloads import RedisJobPayloadStore


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expiries = {}

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return None
        self.values[key] = value
        self.expiries[key] = ex
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        existed = key in self.values
        self.values.pop(key, None)
        self.expiries.pop(key, None)
        return int(existed)


class RedisJobPayloadStoreTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeRedis()
        self.store = RedisJobPayloadStore(
            self.client, namespace="test:payloads", ttl_seconds=90,
            max_payload_bytes=1024,
        )

    def test_round_trip_preserves_binary_tuples_and_nested_metadata(self):
        payload = (
            "vision-studio",
            (b"\x89PNG\r\nimage-bytes", "image/png"),
            {"options": ["fast", True, None], "studio": {"mode": "balanced"}},
        )
        self.assertTrue(self.store.save("job-1", payload))
        self.assertEqual(self.store.load("job-1"), payload)
        self.assertEqual(self.client.expiries["test:payloads:job-1"], 90)

    def test_save_is_idempotent_and_delete_removes_payload(self):
        self.assertTrue(self.store.save("job-1", {"prompt": "first"}))
        self.assertFalse(self.store.save("job-1", {"prompt": "replacement"}))
        self.assertEqual(self.store.load("job-1"), {"prompt": "first"})
        self.assertTrue(self.store.delete("job-1"))
        self.assertFalse(self.store.delete("job-1"))
        self.assertIsNone(self.store.load("job-1"))

    def test_payload_validation_rejects_unsupported_and_non_finite_values(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.store.save("bad", {"file": object()})
        with self.assertRaisesRegex(ValueError, "finite"):
            self.store.save("bad", {"score": float("nan")})
        with self.assertRaisesRegex(ValueError, "keys must be strings"):
            self.store.save("bad", {1: "not-json-key"})

    def test_payload_size_and_job_id_are_bounded(self):
        with self.assertRaisesRegex(ValueError, "storage limit"):
            self.store.save("large", {"blob": b"x" * 2048})
        with self.assertRaises(ValueError):
            self.store.save(" padded ", {"ok": True})

    def test_constructor_rejects_invalid_limits(self):
        for kwargs in (
            {"ttl_seconds": 0},
            {"ttl_seconds": True},
            {"max_payload_bytes": 0},
            {"max_payload_bytes": 1.5},
            {"namespace": ""},
            {"namespace": "bad:"},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    RedisJobPayloadStore(self.client, **kwargs)


class RealRedisJobPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.environ.get("JOB_STORE_REDIS_URL")
        if not url:
            raise unittest.SkipTest("JOB_STORE_REDIS_URL is not configured")
        import redis
        cls.client = redis.Redis.from_url(url, decode_responses=True)
        cls.client.ping()

    def setUp(self):
        self.namespace = "atelier:payload-test:" + uuid.uuid4().hex
        self.store = RedisJobPayloadStore(
            self.client, namespace=self.namespace, ttl_seconds=60
        )

    def tearDown(self):
        for key in self.client.scan_iter(match=self.namespace + "*"):
            self.client.delete(key)

    def test_real_redis_binary_payload_ttl_and_delete(self):
        payload = {"image": (b"private-image-data", "image/jpeg"), "text": "hello"}
        self.assertTrue(self.store.save("one", payload))
        self.assertGreater(self.client.ttl(self.namespace + ":one"), 0)
        self.assertEqual(self.store.load("one"), payload)
        self.assertTrue(self.store.delete("one"))
        self.assertIsNone(self.store.load("one"))


if __name__ == "__main__":
    unittest.main()
