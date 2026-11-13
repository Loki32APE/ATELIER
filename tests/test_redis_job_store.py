"""Redis job store behavioural tests."""
import json
import multiprocessing
import os
import unittest
import uuid
from atelier_engine.job_store import RedisJobStore
from atelier_engine.job_queue import RedisJobQueue

class FakeRedis:
    def __init__(self): self.values, self.zsets, self.expiries = {}, {}, {}
    def eval(self, script, n, *args):
        keys, argv = args[:n], args[n:]
        if "ZCARD" in script:
            rk, ak = keys; cap, payload, ttl, score, jid = argv
            if rk in self.values: return -1
            z=self.zsets.setdefault(ak,{})
            if len(z)>=int(cap): return 0
            self.values[rk]=payload; z[jid]=float(score); return 1
        if "-- atelier:touch" in script:
            rk,ak=keys; timestamp,jid=argv
            if rk not in self.values: return 0
            rec=json.loads(self.values[rk])
            if rec.get("status") != "running": return 0
            self.zsets.setdefault(ak,{})[jid]=float(timestamp)
            return 1
        if "cjson.decode(ARGV[1])" in script:
            rk,ak,fk=keys; fields,finished,jid,ttl=argv
            if rk not in self.values: return 0
            rec=json.loads(self.values[rk])
            if rec.get("status")!="running": return 0
            changes=json.loads(fields); rec.update(changes)
            if changes.get("status") and changes["status"]!="running":
                rec["finished_at"]=float(finished)
                self.zsets.setdefault(ak,{}).pop(jid,None)
                self.zsets.setdefault(fk,{})[jid]=float(rec["finished_at"])
                self.expiries[rk]=int(ttl)
            self.values[rk]=json.dumps(rec); return 1
        rk,ak,fk=keys; jid=argv[0]; exists=rk in self.values
        self.values.pop(rk,None); self.zsets.setdefault(ak,{}).pop(jid,None)
        self.zsets.setdefault(fk,{}).pop(jid,None)
        self.expiries.pop(rk,None); return int(exists)
    def get(self,key): return self.values.get(key)
    def ping(self): return True
    def zcard(self,key): return len(self.zsets.get(key,{}))
    def zadd(self,key,mapping):
        z=self.zsets.setdefault(key,{})
        z.update({member:float(score) for member,score in mapping.items()})
        return len(mapping)
    def zrange(self,key,start,stop):
        items=sorted(self.zsets.get(key,{}).items(),key=lambda item:(item[1],item[0]))
        return [member for member,_ in items[start:] if stop == -1] if stop == -1 else [member for member,_ in items[start:stop+1]]
    def zrangebyscore(self,key,minimum,maximum):
        low=float("-inf") if minimum == "-inf" else float(minimum)
        high=float("inf") if maximum == "+inf" else float(maximum)
        return [member for member,score in sorted(
            self.zsets.get(key,{}).items(),key=lambda item:(item[1],item[0])
        ) if low <= score <= high]
    def zrem(self,key,*members):
        z=self.zsets.setdefault(key,{})
        removed=0
        for member in members:
            removed += int(z.pop(member,None) is not None)
        return removed
    def scan_iter(self,match="*"):
        import fnmatch
        keys = set(self.values) | set(self.zsets)
        return iter(key for key in keys if fnmatch.fnmatch(key,match))

class RedisStoreTests(unittest.TestCase):
    def setUp(self):
        self.client=FakeRedis()
        self.store=RedisJobStore(self.client,namespace="test:jobs",max_active=2,record_ttl_seconds=90)
    def record(self): return {"status":"running","created_at":10,"access_token":"secret"}
    def test_capacity_and_duplicate_reservation(self):
        self.assertTrue(self.store.create("a",self.record()))
        self.assertFalse(self.store.create("a",self.record()))
        self.assertTrue(self.store.create("b",self.record()))
        self.assertFalse(self.store.create("c",self.record()))
        self.assertEqual(self.client.zcard(self.store.active_key),2)
    def test_terminal_update_releases_capacity_and_sets_ttl(self):
        self.store.create("a",self.record())
        self.assertTrue(self.store.update_running("a",{"status":"done"},55))
        self.assertEqual(self.store.snapshot("a")["finished_at"],55)
        self.assertEqual(self.client.zcard(self.store.active_key),0)
        self.assertEqual(self.client.zcard(self.store.finished_key),1)
        self.assertEqual(self.client.expiries["test:jobs:a"],90)
        self.assertFalse(self.store.update_running("a",{"status":"failed"},60))
    def test_running_job_is_not_ttl_expired(self):
        self.store.create("a",self.record())
        self.store.update_running("a",{"progress":20},15)
        self.assertNotIn("test:jobs:a",self.client.expiries)
        self.assertEqual(self.client.zcard(self.store.active_key),1)
    def test_constructor_rejects_invalid_configuration(self):
        for kwargs in (
            {"namespace": ""},
            {"namespace": "test:jobs:"},
            {"max_active": 0},
            {"max_active": 1.5},
            {"record_ttl_seconds": 0},
            {"record_ttl_seconds": True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    RedisJobStore(self.client, **kwargs)

    def test_create_rejects_non_dictionary_record_before_reading_fields(self):
        for record in (None, [], "not-a-record", 42):
            with self.subTest(record=record):
                with self.assertRaisesRegex(ValueError, "dictionary"):
                    self.store.create("invalid-record", record)

    def test_create_validates_job_id_record_and_timestamp(self):
        with self.assertRaises(ValueError):
            self.store.create("bad-created", {**self.record(), "created_at": float("inf")})
        with self.assertRaises(ValueError):
            self.store.create("bad-finished", {**self.record(), "finished_at": "later"})
        with self.assertRaises(ValueError):
            self.store.create("", self.record())
        with self.assertRaises(ValueError):
            self.store.create(" padded ", self.record())
        with self.assertRaises(ValueError):
            self.store.create("bad-state", {"status": "done"})
        with self.assertRaises(ValueError):
            self.store.create("bad-time", {**self.record(), "created_at": float("nan")})
        self.assertEqual(self.client.zcard(self.store.active_key), 0)

    def test_updates_reject_non_finite_values_and_delete_releases_capacity(self):
        self.store.create("a", self.record())
        with self.assertRaises(ValueError):
            self.store.update_running("a", {"progress": float("inf")}, 20)
        with self.assertRaises(ValueError):
            self.store.update_running("a", {"status": "done"}, float("nan"))
        self.assertEqual(self.client.zcard(self.store.active_key), 1)
        self.assertTrue(self.store.delete("a"))
        self.assertEqual(self.client.zcard(self.store.active_key), 0)

    def test_namespaces_isolate_identical_job_ids(self):
        other = RedisJobStore(self.client, namespace="other:jobs", max_active=2)
        self.assertTrue(self.store.create("same", self.record()))
        self.assertTrue(other.create("same", self.record()))
        self.assertIsNotNone(self.store.snapshot("same"))
        self.assertIsNotNone(other.snapshot("same"))
        self.assertNotEqual(self.store._key("same"), other._key("same"))

    def test_liveness_heartbeat_prevents_false_stale_expiry(self):
        self.store.create("live", {"status": "running", "created": 1})
        self.assertTrue(self.store.touch_running("live", 15))
        self.store.maintain(
            now=20, max_runtime_seconds=10,
            finished_ttl_seconds=100, max_records=20,
        )
        self.assertEqual(self.store.snapshot("live")["status"], "running")
        self.store.maintain(
            now=26, max_runtime_seconds=10,
            finished_ttl_seconds=100, max_records=20,
        )
        self.assertEqual(self.store.snapshot("live")["status"], "error")

    def test_active_count_and_maintenance_expire_and_bound_history(self):
        self.store.create("stale", {"status": "running", "created": 1})
        self.store.create("old-done", {"status": "running", "created": 2})
        self.store.update_running("old-done", {"status": "done"}, 2)
        self.store.create("new-done", {"status": "running", "created": 9})
        self.store.update_running("new-done", {"status": "done"}, 9)
        self.assertEqual(self.store.active_count(), 1)
        self.store.maintain(
            now=20, max_runtime_seconds=10,
            finished_ttl_seconds=100, max_records=2,
        )
        self.assertEqual(self.store.snapshot("stale")["status"], "error")
        self.assertIsNone(self.store.snapshot("old-done"))
        self.assertIsNotNone(self.store.snapshot("new-done"))
        self.assertEqual(self.store.active_count(), 0)
        self.assertEqual(self.client.zcard(self.store.finished_key), 2)
        self.assertTrue(self.store.delete("new-done"))
        self.assertEqual(self.client.zcard(self.store.finished_key), 1)
        self.assertTrue(self.store.delete("stale"))
        self.assertEqual(self.client.zcard(self.store.finished_key), 0)

    def test_snapshot_token_delete_and_ping(self):
        self.store.create("a",self.record())
        self.assertEqual(self.store.access_token("a"),"secret")
        snapshot=self.store.snapshot("a"); snapshot["status"]="changed"
        self.assertEqual(self.store.snapshot("a")["status"],"running")
        self.assertTrue(self.store.ping())
        self.assertTrue(self.store.delete("a")); self.assertFalse(self.store.delete("a"))
        self.assertIsNone(self.store.snapshot("a"))




def _create_job_in_process(redis_url, namespace, job_id, gate, output):
    import redis
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    store = RedisJobStore(client, namespace=namespace, max_active=1)
    gate.wait(timeout=10)
    output.put((job_id, store.create(job_id, {
        "status": "running", "created_at": 10, "access_token": job_id,
    })))


class RealRedisIntegrationTests(unittest.TestCase):
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
        self.namespace = "atelier:test:" + uuid.uuid4().hex
        self.store = RedisJobStore(self.client, namespace=self.namespace,
                                   max_active=1, record_ttl_seconds=60)

    def tearDown(self):
        for key in self.client.scan_iter(match=self.namespace + "*"):
            self.client.delete(key)

    def test_two_separate_web_processes_share_atomic_capacity(self):
        context = multiprocessing.get_context("fork")
        gate = context.Event()
        output = context.Queue()
        processes = [
            context.Process(
                target=_create_job_in_process,
                args=(
                    os.environ["JOB_STORE_REDIS_URL"], self.namespace,
                    job_id, gate, output,
                ),
            )
            for job_id in ("process-a", "process-b")
        ]
        for process in processes:
            process.start()
        gate.set()
        results = [output.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(timeout=15)
            self.assertEqual(process.exitcode, 0)
            process.close()
        output.close()
        output.join_thread()
        self.assertEqual(sum(created for _job_id, created in results), 1)
        winning_id = next(job_id for job_id, created in results if created)
        self.assertIsNotNone(self.store.snapshot(winning_id))
        self.assertEqual(self.store.active_count(), 1)

    def test_independent_web_stores_share_records_and_capacity_atomically(self):
        second_web_store = RedisJobStore(
            self.client, namespace=self.namespace,
            max_active=1, record_ttl_seconds=60,
        )
        from concurrent.futures import ThreadPoolExecutor
        record_a = {"status": "running", "created_at": 10, "access_token": "a"}
        record_b = {"status": "running", "created_at": 10, "access_token": "b"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda pair: pair[0].create(pair[1], pair[2]),
                ((self.store, "a", record_a), (second_web_store, "b", record_b)),
            ))
        self.assertEqual(sum(results), 1)
        winning_id = "a" if results[0] else "b"
        self.assertIsNotNone(second_web_store.snapshot(winning_id))
        self.assertEqual(self.store.active_count(), 1)
        self.assertEqual(second_web_store.active_count(), 1)

    def test_fenced_update_rejects_expired_worker_after_new_lease_claim(self):
        queue = RedisJobQueue(
            self.client, namespace=self.namespace + ":queue",
            lease_seconds=5, max_attempts=3,
        )
        self.assertTrue(self.store.create("fenced", {
            "status": "running", "created_at": 100, "access_token": "private",
        }))
        self.assertTrue(queue.enqueue("fenced", available_at=100))
        first = queue.claim(now=100)
        self.assertEqual(first["attempt"], 1)
        self.assertTrue(self.store.update_running_with_lease(
            "fenced", {"step": "first worker"}, 101,
            queue=queue, lease_token=first["lease_token"],
        ))

        # A second worker recovers the expired lease and receives a new token.
        second = queue.claim(now=107)
        self.assertEqual(second["attempt"], 2)
        self.assertFalse(self.store.update_running_with_lease(
            "fenced", {"status": "done", "prompt": "stale result"}, 108,
            queue=queue, lease_token=first["lease_token"],
        ))
        self.assertTrue(self.store.update_running_with_lease(
            "fenced", {"status": "done", "prompt": "current result"}, 108,
            queue=queue, lease_token=second["lease_token"],
        ))
        self.assertEqual(self.store.snapshot("fenced")["prompt"], "current result")
        self.assertTrue(queue.acknowledge("fenced", second["lease_token"], now=109))

    def test_lua_capacity_and_terminal_ttl(self):
        record = {"status": "running", "created_at": 10, "access_token": "private"}
        self.assertTrue(self.store.create("one", record))
        self.assertFalse(self.store.create("two", record))
        self.assertEqual(self.client.ttl(self.namespace + ":one"), -1)
        self.assertTrue(self.store.update_running("one", {"status": "done"}, 22))
        self.assertEqual(self.client.zcard(self.store.active_key), 0)
        self.assertGreater(self.client.ttl(self.namespace + ":one"), 0)
        self.assertEqual(self.store.snapshot("one")["finished_at"], 22)
        self.assertTrue(self.store.create("two", record))

    def test_lua_finished_index_and_maintenance_retention(self):
        old = {"status": "running", "created_at": 10, "access_token": "private"}
        stale = {"status": "running", "created_at": 1, "access_token": "private"}
        self.assertTrue(self.store.create("old", old))
        self.assertTrue(self.store.update_running("old", {"status": "done"}, 22))
        self.assertTrue(self.store.create("stale", stale))
        self.store.maintain(
            now=100, max_runtime_seconds=10,
            finished_ttl_seconds=1000, max_records=1,
        )
        self.assertIsNone(self.store.snapshot("old"))
        self.assertEqual(self.store.snapshot("stale")["status"], "error")
        self.assertEqual(self.client.zcard(self.store.finished_key), 1)

if __name__=="__main__": unittest.main()
