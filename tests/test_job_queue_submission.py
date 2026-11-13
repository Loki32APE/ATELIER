"""Tests for the Flask app's opt-in durable queue submission path."""
import unittest
from unittest.mock import patch

import app as atelier_app


class FakeJobStore:
    def __init__(self):
        self.deleted = []
        self.updated = []

    def delete(self, job_id):
        self.deleted.append(job_id)
        return True

    def update_running(self, job_id, fields, finished_at):
        self.updated.append((job_id, fields))
        return True


class FakePayloadStore:
    def __init__(self, save_result=True):
        self.save_result = save_result
        self.saved = []
        self.deleted = []

    def save(self, job_id, payload):
        self.saved.append((job_id, payload))
        return self.save_result

    def delete(self, job_id):
        self.deleted.append(job_id)
        return True


class FakeQueue:
    def __init__(self, enqueue_result=True, heartbeat_result=True):
        self.enqueue_result = enqueue_result
        self.heartbeat_result = heartbeat_result
        self.enqueued = []

    def heartbeat(self, job_id, token):
        return self.heartbeat_result

    def enqueue(self, job_id, *, available_at):
        self.enqueued.append((job_id, available_at))
        return self.enqueue_result


def run_generate_job(*_args):
    pass


class DurableQueueSubmissionTests(unittest.TestCase):
    def test_durable_submission_persists_allowlisted_payload_then_enqueues_id(self):
        payloads = FakePayloadStore()
        queue = FakeQueue()
        store = FakeJobStore()
        args = ("job-1", (b"image-bytes", "image/png"), "subject")
        with (
            patch.object(atelier_app, "JOB_QUEUE_ENABLED", True),
            patch.object(atelier_app, "job_payload_store", payloads),
            patch.object(atelier_app, "job_queue", queue),
            patch.object(atelier_app, "job_store", store),
        ):
            self.assertTrue(atelier_app.start_job_worker("job-1", run_generate_job, args))
        self.assertEqual(payloads.saved, [(
            "job-1", {"handler": "run_generate_job", "args": args}
        )])
        self.assertEqual(len(queue.enqueued), 1)
        self.assertEqual(queue.enqueued[0][0], "job-1")
        self.assertEqual(store.deleted, [])

    def test_queue_failure_cleans_payload_and_reserved_job(self):
        payloads = FakePayloadStore()
        queue = FakeQueue(enqueue_result=False)
        store = FakeJobStore()
        with (
            patch.object(atelier_app, "JOB_QUEUE_ENABLED", True),
            patch.object(atelier_app, "job_payload_store", payloads),
            patch.object(atelier_app, "job_queue", queue),
            patch.object(atelier_app, "job_store", store),
        ):
            self.assertFalse(atelier_app.start_job_worker("job-2", run_generate_job, ("job-2",)))
        self.assertEqual(payloads.deleted, ["job-2"])
        self.assertEqual(store.deleted, ["job-2"])

    def test_stale_worker_lease_cannot_update_job_status(self):
        queue = FakeQueue(heartbeat_result=False)
        store = FakeJobStore()
        lease_context = atelier_app.current_worker_lease.set(("job-4", "stale-token"))
        try:
            with (
                patch.object(atelier_app, "job_queue", queue),
                patch.object(atelier_app, "job_store", store),
            ):
                self.assertFalse(atelier_app.set_job("job-4", status="done"))
        finally:
            atelier_app.current_worker_lease.reset(lease_context)
        self.assertEqual(store.updated, [])

    def test_non_allowlisted_handler_is_rejected(self):
        payloads = FakePayloadStore()
        queue = FakeQueue()
        store = FakeJobStore()
        with (
            patch.object(atelier_app, "JOB_QUEUE_ENABLED", True),
            patch.object(atelier_app, "job_payload_store", payloads),
            patch.object(atelier_app, "job_queue", queue),
            patch.object(atelier_app, "job_store", store),
        ):
            self.assertFalse(atelier_app.start_job_worker("job-3", lambda: None, ()))
        self.assertEqual(payloads.saved, [])
        self.assertEqual(queue.enqueued, [])
        self.assertEqual(store.deleted, ["job-3"])


if __name__ == "__main__":
    unittest.main()
