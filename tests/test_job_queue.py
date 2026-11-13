"""Behavioural and real-Redis tests for the durable leased job queue."""
import fnmatch
import os
import unittest
import uuid

from atelier_engine.job_queue import RedisJobQueue


class FakeQueueRedis:
    def __init__(self):
        self.zsets = {}
        self.hashes = {}
        self.values = {}
        self.expiries = {}

    def exists(self, key):
        return int(key in self.values)

    def zscore(self, key, member):
        return self.zsets.get(key, {}).get(member)

    def zadd(self, key, mapping, nx=False):
        target = self.zsets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            if nx and member in target:
                continue
            added += int(member not in target)
            target[member] = float(score)
        return added

    def zrem(self, key, *members):
        target = self.zsets.setdefault(key, {})
        removed = 0
        for member in members:
            removed += int(target.pop(member, None) is not None)
        return removed

    def zcard(self, key):
        return len(self.zsets.get(key, {}))

    def zrange(self, key, start, stop):
        items = sorted(
            self.zsets.get(key, {}).items(),
            key=lambda item: (item[1], item[0]),
        )
        selected = items[start:] if stop == -1 else items[start:stop + 1]
        return [member for member, _score in selected]

    def zrangebyscore(self, key, minimum, maximum, start=None, num=None):
        low = float("-inf") if minimum == "-inf" else float(minimum)
        high = float("inf") if maximum == "+inf" else float(maximum)
        found = [member for member, score in sorted(
            self.zsets.get(key, {}).items(), key=lambda item: (item[1], item[0])
        ) if low <= score <= high]
        if start is not None:
            found = found[start:start + num]
        return found

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = str(value)
        return 1

    def hdel(self, key, field):
        return int(self.hashes.setdefault(key, {}).pop(field, None) is not None)

    def hincrby(self, key, field, amount):
        value = int(self.hget(key, field) or 0) + int(amount)
        self.hset(key, field, value)
        return value

    def set(self, key, value, ex=None):
        self.values[key] = value
        self.expiries[key] = ex
        return True

    def ping(self):
        return True

    def eval(self, script, key_count, *args):
        keys, argv = args[:key_count], args[key_count:]
        if "-- atelier:enqueue" in script:
            pending, leases, _tokens, _attempts, dead, done = keys
            job_id, available_at = argv
            if self.exists(done) or any(
                self.zscore(key, job_id) is not None for key in (pending, leases, dead)
            ):
                return 0
            self.zadd(pending, {job_id: float(available_at)}, nx=True)
            return 1
        if "-- atelier:claim" in script:
            pending, leases, tokens, attempts = keys
            now, token, expiry = argv
            due = self.zrangebyscore(pending, "-inf", now, start=0, num=1)
            if not due:
                return None
            job_id = due[0]
            self.zrem(pending, job_id)
            attempt = self.hincrby(attempts, job_id, 1)
            self.hset(tokens, job_id, token)
            self.zadd(leases, {job_id: float(expiry)})
            return [job_id, str(attempt)]
        if "-- atelier:heartbeat" in script:
            leases, tokens = keys
            job_id, token, now, expiry = argv
            current = self.zscore(leases, job_id)
            if self.hget(tokens, job_id) != token or current is None or current <= float(now):
                return 0
            self.zadd(leases, {job_id: float(expiry)})
            return 1
        if "-- atelier:ack" in script:
            done, leases, tokens, attempts = keys
            job_id, token, ttl, now = argv
            expiry = self.zscore(leases, job_id)
            if self.hget(tokens, job_id) != token or expiry is None or expiry <= float(now):
                return 0
            self.zrem(leases, job_id)
            self.hdel(tokens, job_id)
            self.hdel(attempts, job_id)
            self.set(done, "1", ex=int(ttl))
            return 1
        if "-- atelier:retry" in script:
            pending, leases, tokens, attempts, dead = keys
            job_id, token, available_at, _score, max_attempts, now = argv
            expiry = self.zscore(leases, job_id)
            if self.hget(tokens, job_id) != token or expiry is None or expiry <= float(now):
                return 0
            self.zrem(leases, job_id)
            self.hdel(tokens, job_id)
            attempt = int(self.hget(attempts, job_id) or 0)
            if attempt >= int(max_attempts):
                self.zadd(dead, {job_id: float(available_at)})
                return 2
            self.zadd(pending, {job_id: float(available_at)})
            return 1
        if "-- atelier:recover" in script:
            pending, leases, tokens, attempts, dead = keys
            now, available_at, max_attempts, batch_size = argv
            expired = self.zrangebyscore(leases, "-inf", now, start=0, num=int(batch_size))
            for job_id in expired:
                self.zrem(leases, job_id)
                self.hdel(tokens, job_id)
                attempt = int(self.hget(attempts, job_id) or 0)
                if attempt >= int(max_attempts):
                    self.zadd(dead, {job_id: float(now)})
                else:
                    self.zadd(pending, {job_id: float(available_at)})
            return len(expired)
        if "-- atelier:discard-dead" in script:
            dead, attempts = keys
            job_id = argv[0]
            removed = self.zrem(dead, job_id)
            self.hdel(attempts, job_id)
            return removed
        raise AssertionError("Unknown Lua script")

    def scan_iter(self, match="*"):
        keys = set(self.values) | set(self.zsets) | set(self.hashes)
        return iter(key for key in keys if fnmatch.fnmatch(key, match))


class RedisJobQueueTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeQueueRedis()
        self.queue = RedisJobQueue(
            self.client, namespace="test:queue", lease_seconds=10,
            max_attempts=3, completed_ttl_seconds=60,
        )

    def test_enqueue_claim_heartbeat_and_ack_are_token_protected(self):
        self.assertTrue(self.queue.enqueue("job-1", available_at=100))
        self.assertFalse(self.queue.enqueue("job-1", available_at=100))
        claim = self.queue.claim(now=100)
        self.assertEqual(claim["job_id"], "job-1")
        self.assertEqual(claim["attempt"], 1)
        self.assertTrue(self.queue.heartbeat("job-1", claim["lease_token"], now=105))
        self.assertFalse(self.queue.acknowledge("job-1", "wrong-token", now=106))
        self.assertTrue(self.queue.acknowledge("job-1", claim["lease_token"], now=106))
        self.assertFalse(self.queue.enqueue("job-1", available_at=107))
        self.assertEqual(self.queue.leased_count(), 0)

    def test_expired_lease_recovery_rejects_stale_worker_and_retries(self):
        self.queue.enqueue("job-2", available_at=100)
        first = self.queue.claim(now=100)
        self.assertFalse(self.queue.heartbeat("job-2", first["lease_token"], now=110))
        second = self.queue.claim(now=111)
        self.assertEqual(second["attempt"], 2)
        self.assertNotEqual(first["lease_token"], second["lease_token"])
        self.assertFalse(self.queue.acknowledge("job-2", first["lease_token"], now=112))
        self.assertEqual(
            self.queue.retry("job-2", second["lease_token"], available_at=120, now=112),
            "queued",
        )
        self.assertIsNone(self.queue.claim(now=119))
        third = self.queue.claim(now=120)
        self.assertEqual(third["attempt"], 3)
        self.assertEqual(
            self.queue.retry("job-2", third["lease_token"], available_at=121, now=121-0.1),
            "dead",
        )
        self.assertEqual(self.queue.dead_count(), 1)
        self.assertEqual(self.queue.dead_jobs(), ["job-2"])
        self.assertTrue(self.queue.discard_dead("job-2"))
        self.assertEqual(self.queue.dead_count(), 0)

    def test_expired_max_attempt_lease_moves_to_dead_letter(self):
        self.queue.enqueue("job-3", available_at=1)
        for expected_attempt, now in enumerate((1, 12, 23), start=1):
            claim = self.queue.claim(now=now)
            self.assertEqual(claim["attempt"], expected_attempt)
            if now != 23:
                self.assertEqual(self.queue.recover_expired(now=now + 11), 1)
        self.assertEqual(self.queue.recover_expired(now=34), 1)
        self.assertEqual(self.queue.dead_count(), 1)
        self.assertEqual(self.queue.dead_jobs(), ["job-3"])
        self.assertEqual(self.queue.pending_count(), 0)

    def test_expired_lease_recovery_is_bounded_per_batch(self):
        queue = RedisJobQueue(
            self.client, namespace="test:bounded", lease_seconds=1,
            max_attempts=3, recovery_batch_size=2,
        )
        for job_id in ("a", "b", "c"):
            queue.enqueue(job_id, available_at=1)
            queue.claim(now=1)
        self.assertEqual(queue.recover_expired(now=3), 2)
        self.assertEqual(queue.leased_count(), 1)
        self.assertEqual(queue.pending_count(), 2)
        self.assertEqual(queue.recover_expired(now=3), 1)
        self.assertEqual(queue.leased_count(), 0)
        self.assertEqual(queue.pending_count(), 3)

    def test_constructor_and_input_validation(self):
        for kwargs in (
            {"namespace": ""},
            {"namespace": "bad:"},
            {"lease_seconds": 0},
            {"max_attempts": True},
            {"completed_ttl_seconds": 1.5},
            {"recovery_batch_size": 0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    RedisJobQueue(self.client, **kwargs)
        with self.assertRaises(ValueError):
            self.queue.enqueue(" padded ", available_at=1)
        with self.assertRaises(ValueError):
            self.queue.enqueue("valid", available_at=float("nan"))
        with self.assertRaises(ValueError):
            self.queue.heartbeat("valid", "", now=1)


class RealRedisJobQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.environ.get("JOB_STORE_REDIS_URL")
        if not url:
            raise unittest.SkipTest("JOB_STORE_REDIS_URL is not configured")
        import redis
        cls.client = redis.Redis.from_url(url, decode_responses=True)
        cls.client.ping()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        super().tearDownClass()

    def setUp(self):
        self.namespace = "atelier:queue-test:" + uuid.uuid4().hex
        self.queue = RedisJobQueue(
            self.client, namespace=self.namespace, lease_seconds=3,
            max_attempts=2, completed_ttl_seconds=30,
        )

    def tearDown(self):
        for key in self.client.scan_iter(match=self.namespace + "*"):
            self.client.delete(key)

    def test_independent_worker_recovers_expired_lease_after_restart(self):
        second_worker_queue = RedisJobQueue(
            self.client, namespace=self.namespace, lease_seconds=3,
            max_attempts=2, completed_ttl_seconds=30,
        )
        self.assertTrue(self.queue.enqueue("restart", available_at=100))
        first_claim = self.queue.claim(now=100)
        self.assertEqual(first_claim["attempt"], 1)
        restarted_claim = second_worker_queue.claim(now=104)
        self.assertEqual(restarted_claim["job_id"], "restart")
        self.assertEqual(restarted_claim["attempt"], 2)
        self.assertFalse(self.queue.acknowledge(
            "restart", first_claim["lease_token"], now=105
        ))
        self.assertTrue(second_worker_queue.acknowledge(
            "restart", restarted_claim["lease_token"], now=105
        ))

    def test_independent_workers_cannot_claim_the_same_pending_job(self):
        from concurrent.futures import ThreadPoolExecutor
        second_worker_queue = RedisJobQueue(
            self.client, namespace=self.namespace, lease_seconds=30,
            max_attempts=3, completed_ttl_seconds=30,
        )
        self.assertTrue(self.queue.enqueue("concurrent", available_at=100))
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(
                lambda queue: queue.claim(now=100),
                (self.queue, second_worker_queue),
            ))
        self.assertEqual(sum(claim is not None for claim in claims), 1)
        self.assertEqual(self.queue.leased_count(), 1)

    def test_real_redis_recovery_processes_only_configured_batch(self):
        queue = RedisJobQueue(
            self.client, namespace=self.namespace, lease_seconds=2,
            max_attempts=3, recovery_batch_size=1,
        )
        for job_id in ("one", "two"):
            queue.enqueue(job_id, available_at=100)
            queue.claim(now=100)
        self.assertEqual(queue.recover_expired(now=103), 1)
        self.assertEqual(queue.leased_count(), 1)
        self.assertEqual(queue.pending_count(), 1)
        self.assertEqual(queue.recover_expired(now=103), 1)
        self.assertEqual(queue.leased_count(), 0)
        self.assertEqual(queue.pending_count(), 2)

    def test_real_redis_claim_lease_recovery_retry_and_ack(self):
        self.assertTrue(self.queue.enqueue("one", available_at=100))
        claim = self.queue.claim(now=100)
        self.assertEqual(claim["attempt"], 1)
        self.assertTrue(self.queue.heartbeat("one", claim["lease_token"], now=101))
        self.assertFalse(self.queue.acknowledge("one", claim["lease_token"], now=105))
        recovered = self.queue.claim(now=105)
        self.assertEqual(recovered["attempt"], 2)
        self.assertFalse(self.queue.acknowledge("one", claim["lease_token"], now=106))
        self.assertEqual(
            self.queue.retry("one", recovered["lease_token"], available_at=107, now=106),
            "dead",
        )
        self.assertEqual(self.queue.dead_count(), 1)
        self.assertEqual(self.queue.dead_jobs(), ["one"])
        self.assertTrue(self.queue.discard_dead("one"))
        self.assertEqual(self.queue.dead_count(), 0)


if __name__ == "__main__":
    unittest.main()
