"""Contract tests for job-store adapters."""
import unittest

from atelier_engine.job_store import InMemoryJobStore


class InMemoryJobStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryJobStore()

    def test_create_and_snapshot_return_isolated_records(self):
        record = {"status": "running", "nested": {"items": ["original"]}}
        self.assertTrue(self.store.create("job-1", record))
        record["nested"]["items"].append("caller-change")
        snapshot = self.store.snapshot("job-1")
        self.assertEqual(snapshot["nested"]["items"], ["original"])
        snapshot["nested"]["items"].append("snapshot-change")
        self.assertEqual(self.store.snapshot("job-1")["nested"]["items"], ["original"])

    def test_create_rejects_duplicate_identifiers(self):
        self.assertTrue(self.store.create("job-1", {"status": "running"}))
        self.assertFalse(self.store.create("job-1", {"status": "done"}))
        self.assertEqual(self.store.snapshot("job-1")["status"], "running")

    def test_update_only_changes_running_jobs(self):
        self.store.create("job-1", {"status": "running", "created": 10})
        self.assertTrue(self.store.update_running(
            "job-1", {"status": "done", "prompt": "result"}, finished_at=25
        ))
        self.assertEqual(self.store.snapshot("job-1")["finished_at"], 25)
        self.assertFalse(self.store.update_running(
            "job-1", {"status": "done", "prompt": "late result"}, finished_at=30
        ))
        self.assertEqual(self.store.snapshot("job-1")["prompt"], "result")

    def test_nonterminal_update_does_not_stamp_finished_at(self):
        self.store.create("job-1", {"status": "running", "finished_at": None})
        self.assertTrue(self.store.update_running(
            "job-1", {"step": "Working"}, finished_at=25
        ))
        self.assertIsNone(self.store.snapshot("job-1")["finished_at"])

    def test_access_token_is_internal_and_missing_job_returns_none(self):
        self.store.create("job-1", {"status": "running", "access_token": "secret-token"})
        self.assertEqual(self.store.access_token("job-1"), "secret-token")
        self.assertIsNone(self.store.access_token("missing"))

    def test_delete_reports_whether_record_existed(self):
        self.store.create("job-1", {"status": "running"})
        self.assertTrue(self.store.delete("job-1"))
        self.assertFalse(self.store.delete("job-1"))
        self.assertIsNone(self.store.snapshot("job-1"))

    def test_touch_running_refreshes_liveness_and_rejects_terminal_jobs(self):
        self.store.create("job-1", {"status": "running", "created": 1})
        self.assertTrue(self.store.touch_running("job-1", 9))
        self.assertEqual(self.store.snapshot("job-1")["last_activity_at"], 9)
        self.assertTrue(self.store.update_running("job-1", {"status": "done"}, 10))
        self.assertFalse(self.store.touch_running("job-1", 11))

    def test_active_count_and_maintenance_expire_and_bound_history(self):
        self.store.create("stale", {"status": "running", "created": 1})
        self.store.create("old-done", {"status": "done", "created": 2, "finished_at": 2})
        self.store.create("new-done", {"status": "done", "created": 9, "finished_at": 9})
        self.assertEqual(self.store.active_count(), 1)
        self.store.maintain(
            now=20, max_runtime_seconds=10,
            finished_ttl_seconds=100, max_records=2,
        )
        self.assertEqual(self.store.snapshot("stale")["status"], "error")
        self.assertIsNone(self.store.snapshot("old-done"))
        self.assertIsNotNone(self.store.snapshot("new-done"))
        self.assertEqual(self.store.active_count(), 0)


if __name__ == "__main__":
    unittest.main()


class RedisJobStoreContractTests(unittest.TestCase):
    def test_redis_adapter_requires_json_compatible_records(self):
        from atelier_engine.job_store import RedisJobStore

        class UnusedClient:
            def eval(self, *args):
                raise AssertionError("serialization must fail before Redis access")

        store = RedisJobStore(UnusedClient())
        with self.assertRaisesRegex(ValueError, "JSON-compatible"):
            store.create("job-1", {"status": "running", "payload": object()})

    def test_redis_adapter_validates_capacity_and_retention(self):
        from atelier_engine.job_store import RedisJobStore

        with self.assertRaises(ValueError):
            RedisJobStore(object(), max_active=0)
        with self.assertRaises(ValueError):
            RedisJobStore(object(), record_ttl_seconds=0)

    def test_redis_adapter_rejects_non_running_initial_state(self):
        from atelier_engine.job_store import RedisJobStore

        store = RedisJobStore(object())
        with self.assertRaisesRegex(ValueError, "running state"):
            store.create("job-1", {"status": "done"})
