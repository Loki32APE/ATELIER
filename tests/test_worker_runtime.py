"""Unit tests for the supervised worker runtime."""
import unittest

from atelier_engine.worker_runtime import RedisJobWorker


class FakeQueue:
    lease_seconds = 30

    def __init__(self, outcome="queued", heartbeat_ok=True):
        self.max_attempts = 1 if outcome == "dead" else 3
        self.claim_data = {
            "job_id": "job-1", "lease_token": "lease-1", "attempt": 1,
        }
        self.outcome = outcome
        self.heartbeat_ok = heartbeat_ok
        self.acked = []
        self.retried = []
        self.heartbeats = []

    def claim(self):
        claim, self.claim_data = self.claim_data, None
        return claim

    def heartbeat(self, job_id, token):
        self.heartbeats.append((job_id, token))
        return self.heartbeat_ok

    def acknowledge(self, job_id, token):
        self.acked.append((job_id, token))
        return True

    def retry(self, job_id, token, *, available_at):
        self.retried.append((job_id, token, available_at))
        return self.outcome


class FakePayloadStore:
    def __init__(self, payload):
        self.payload = payload
        self.deleted = []

    def load(self, job_id):
        return self.payload

    def delete(self, job_id):
        self.deleted.append(job_id)
        return True


class FakeJobStore:
    def __init__(self, status="running"):
        self.record = {"status": status}
        self.updates = []

    def snapshot(self, job_id):
        return dict(self.record)

    def update_running(self, job_id, fields, finished_at):
        if self.record["status"] != "running":
            return False
        self.record.update(fields)
        self.updates.append((job_id, dict(fields)))
        return True


class RedisJobWorkerTests(unittest.TestCase):
    def make_worker(self, handler, *, outcome="queued", payload=None, status="running",
                    heartbeat_ok=True):
        queue = FakeQueue(outcome=outcome, heartbeat_ok=heartbeat_ok)
        payloads = FakePayloadStore(
            payload if payload is not None else {"handler": "task", "args": ["job-1"]}
        )
        jobs = FakeJobStore(status=status)
        worker = RedisJobWorker(
            queue, payloads, jobs, {"task": handler},
            heartbeat_interval_seconds=10, retry_backoff_seconds=0,
        )
        return worker, queue, payloads, jobs

    def test_successful_handler_acknowledges_and_deletes_payload(self):
        def handler(job_id):
            jobs.record.update({"status": "done", "result": job_id})
        worker, queue, payloads, jobs = self.make_worker(handler)
        self.assertTrue(worker.run_once())
        self.assertEqual(jobs.record["status"], "done")
        self.assertEqual(queue.acked, [("job-1", "lease-1")])
        self.assertEqual(payloads.deleted, ["job-1"])

    def test_unexpected_failure_is_requeued_and_payload_is_preserved(self):
        def handler(_job_id):
            raise RuntimeError("transient")
        worker, queue, payloads, jobs = self.make_worker(handler)
        self.assertTrue(worker.run_once())
        self.assertEqual(len(queue.retried), 1)
        self.assertEqual(queue.acked, [])
        self.assertEqual(payloads.deleted, [])
        self.assertEqual(jobs.record["status"], "running")

    def test_dead_letter_failure_marks_job_error_and_deletes_payload(self):
        def handler(_job_id):
            raise RuntimeError("permanent")
        worker, queue, payloads, jobs = self.make_worker(handler, outcome="dead")
        self.assertTrue(worker.run_once())
        self.assertEqual(jobs.record["status"], "error")
        self.assertEqual(payloads.deleted, ["job-1"])

    def test_missing_payload_is_terminal_and_acknowledged(self):
        worker, queue, payloads, jobs = self.make_worker(lambda _job_id: None, payload=None)
        payloads.payload = None
        self.assertTrue(worker.run_once())
        self.assertEqual(jobs.record["status"], "error")
        self.assertEqual(queue.acked, [("job-1", "lease-1")])
        self.assertEqual(payloads.deleted, ["job-1"])

    def test_unknown_handler_is_rejected_without_execution(self):
        called = []
        worker, queue, payloads, jobs = self.make_worker(
            lambda _job_id: called.append(True),
            payload={"handler": "unregistered", "args": ["job-1"]},
        )
        self.assertTrue(worker.run_once())
        self.assertEqual(called, [])
        self.assertEqual(jobs.record["status"], "error")
        self.assertEqual(queue.acked, [("job-1", "lease-1")])

    def test_lost_lease_does_not_acknowledge_or_delete_payload(self):
        worker, queue, payloads, jobs = self.make_worker(
            lambda _job_id: None,
            heartbeat_ok=False,
        )
        self.assertTrue(worker.run_once())
        self.assertEqual(queue.acked, [])
        self.assertEqual(payloads.deleted, [])

    def test_empty_queue_returns_false(self):
        worker, queue, payloads, jobs = self.make_worker(lambda _job_id: None)
        queue.claim_data = None
        self.assertFalse(worker.run_once())


if __name__ == "__main__":
    unittest.main()
