"""Real Redis end-to-end test for queue, payload storage, and worker runtime."""
import multiprocessing
import os
import time
import unittest
import uuid

from atelier_engine.job_payloads import RedisJobPayloadStore
from atelier_engine.job_queue import RedisJobQueue
from atelier_engine.job_store import InMemoryJobStore
from atelier_engine.worker_runtime import RedisJobWorker





def _run_worker_process(redis_url, namespace, result_queue):
    import redis
    from atelier_engine.job_payloads import RedisJobPayloadStore
    from atelier_engine.job_queue import RedisJobQueue
    from atelier_engine.job_store import RedisJobStore
    from atelier_engine.worker_runtime import RedisJobWorker

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    queue = RedisJobQueue(client, namespace=namespace + ":queue", lease_seconds=6)
    payloads = RedisJobPayloadStore(client, namespace=namespace + ":payloads", ttl_seconds=60)
    jobs = RedisJobStore(client, namespace=namespace + ":jobs", max_active=2)

    def complete(job_id):
        if not jobs.update_running(
            job_id, {"status": "done", "result": "completed-in-child-process"},
            finished_at=time.time(),
        ):
            raise RuntimeError("child worker could not commit job result")

    worker = RedisJobWorker(
        queue, payloads, jobs, {"complete": complete},
        heartbeat_interval_seconds=1,
    )
    result_queue.put(worker.run_once())




def _run_flask_submission_process(redis_url, namespace, output):
    import importlib
    import app as atelier_app

    os.environ.update({
        "JOB_QUEUE_ENABLED": "true",
        "JOB_STORE_REDIS_URL": redis_url,
        "JOB_STORE_NAMESPACE": namespace + ":jobs",
        "JOB_PAYLOAD_NAMESPACE": namespace + ":payloads",
        "JOB_QUEUE_NAMESPACE": namespace + ":queue",
        "OPENROUTER_API_KEY": "integration-test-key",
    })
    atelier_app = importlib.reload(atelier_app)
    client = atelier_app.app.test_client()
    response = client.post("/vision-lab/generate", json={
        "mode": "advanced",
        "instructions": "Keep the blue coat.",
        "selections": {"outfit_styling": {"description": "Blue coat"}},
    })
    output.put((response.status_code, response.get_json()))


def _run_flask_worker_process(redis_url, namespace, job_id, output):
    import importlib
    import app as atelier_app
    from atelier_engine.worker_runtime import RedisJobWorker

    os.environ.update({
        "JOB_QUEUE_ENABLED": "true",
        "JOB_STORE_REDIS_URL": redis_url,
        "JOB_STORE_NAMESPACE": namespace + ":jobs",
        "JOB_PAYLOAD_NAMESPACE": namespace + ":payloads",
        "JOB_QUEUE_NAMESPACE": namespace + ":queue",
        "OPENROUTER_API_KEY": "integration-test-key",
    })
    atelier_app = importlib.reload(atelier_app)

    def run_vision_lab_job(job_id, _draft, _model, _target):
        if not atelier_app.set_job(
            job_id, status="done", step="", prompt="completed across processes"
        ):
            raise RuntimeError("web worker could not commit terminal job result")

    worker = RedisJobWorker(
        atelier_app.job_queue,
        atelier_app.job_payload_store,
        atelier_app.job_store,
        {"run_vision_lab_job": run_vision_lab_job},
        heartbeat_interval_seconds=1,
    )
    output.put(worker.run_once())



def _run_hanging_worker_process(redis_url, namespace, started):
    import redis
    from atelier_engine.job_payloads import RedisJobPayloadStore
    from atelier_engine.job_queue import RedisJobQueue
    from atelier_engine.job_store import RedisJobStore
    from atelier_engine.worker_runtime import RedisJobWorker

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    queue = RedisJobQueue(
        client, namespace=namespace + ":queue", lease_seconds=2, max_attempts=2
    )
    payloads = RedisJobPayloadStore(
        client, namespace=namespace + ":payloads", ttl_seconds=60
    )
    jobs = RedisJobStore(client, namespace=namespace + ":jobs", max_active=2)

    def hang(_job_id):
        started.set()
        while True:
            time.sleep(0.1)

    worker = RedisJobWorker(
        queue, payloads, jobs, {"hang": hang},
        heartbeat_interval_seconds=0.5,
    )
    worker.run_once()




def _poll_flask_job_process(redis_url, namespace, job_id, access_token, output):
    import importlib
    import app as atelier_app

    os.environ.update({
        "JOB_QUEUE_ENABLED": "true",
        "JOB_STORE_REDIS_URL": redis_url,
        "JOB_STORE_NAMESPACE": namespace + ":jobs",
        "JOB_PAYLOAD_NAMESPACE": namespace + ":payloads",
        "JOB_QUEUE_NAMESPACE": namespace + ":queue",
        "OPENROUTER_API_KEY": "integration-test-key",
    })
    atelier_app = importlib.reload(atelier_app)
    response = atelier_app.app.test_client().get(
        "/status/" + job_id,
        headers={"Authorization": "Bearer " + access_token},
    )
    output.put((response.status_code, response.get_json()))


class RedisWorkerIntegrationTests(unittest.TestCase):
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
        self.namespace = "atelier:worker-e2e:" + uuid.uuid4().hex
        self.queue = RedisJobQueue(
            self.client, namespace=self.namespace + ":queue",
            lease_seconds=5, max_attempts=2, completed_ttl_seconds=30,
        )
        self.payloads = RedisJobPayloadStore(
            self.client, namespace=self.namespace + ":payloads", ttl_seconds=60
        )
        self.jobs = InMemoryJobStore()
        self.job_id = uuid.uuid4().hex

    def tearDown(self):
        for key in self.client.scan_iter(match=self.namespace + "*"):
            self.client.delete(key)

    def test_worker_restart_finalizes_exhausted_expired_leases(self):
        job_id = uuid.uuid4().hex
        self.jobs.create(job_id, {"status": "running", "created": time.time()})
        self.payloads.save(job_id, {"handler": "never-run", "args": [job_id]})
        self.queue.enqueue(job_id, available_at=100)
        first = self.queue.claim(now=100)
        self.assertEqual(first["attempt"], 1)
        second = self.queue.claim(now=106)
        self.assertEqual(second["attempt"], 2)

        restarted_worker = RedisJobWorker(
            self.queue, self.payloads, self.jobs, {},
            heartbeat_interval_seconds=1,
        )
        self.assertFalse(restarted_worker.run_once())
        self.assertEqual(self.jobs.snapshot(job_id)["status"], "error")
        self.assertIsNone(self.payloads.load(job_id))
        self.assertEqual(self.queue.dead_count(), 0)

    def test_killed_worker_is_recovered_by_a_restarted_worker(self):
        from atelier_engine.job_store import RedisJobStore
        from atelier_engine.worker_runtime import current_worker_lease

        queue = RedisJobQueue(
            self.client, namespace=self.namespace + ":queue",
            lease_seconds=2, max_attempts=2, completed_ttl_seconds=30,
        )
        jobs = RedisJobStore(
            self.client, namespace=self.namespace + ":jobs", max_active=2
        )
        job_id = uuid.uuid4().hex
        jobs.create(job_id, {"status": "running", "created": time.time()})
        self.payloads.save(job_id, {"handler": "hang", "args": [job_id]})
        queue.enqueue(job_id, available_at=time.time())

        context = multiprocessing.get_context("fork")
        started = context.Event()
        crashed_worker = context.Process(
            target=_run_hanging_worker_process,
            args=(os.environ["JOB_STORE_REDIS_URL"], self.namespace, started),
        )
        crashed_worker.start()
        self.assertTrue(started.wait(timeout=15))
        crashed_worker.terminate()
        crashed_worker.join(timeout=10)
        self.assertIsNotNone(crashed_worker.exitcode)
        crashed_worker.close()

        time.sleep(2.2)

        def complete_after_restart(claimed_job_id):
            lease = current_worker_lease.get()
            self.assertEqual(claimed_job_id, job_id)
            self.assertIsNotNone(lease)
            self.assertTrue(jobs.update_running_with_lease(
                job_id, {"status": "done", "result": "recovered-after-worker-kill"},
                time.time(), queue=queue, lease_token=lease[1],
            ))

        restarted = RedisJobWorker(
            queue, self.payloads, jobs,
            {"hang": complete_after_restart},
            heartbeat_interval_seconds=0.5,
        )
        self.assertTrue(restarted.run_once())
        self.assertEqual(jobs.snapshot(job_id)["status"], "done")
        self.assertEqual(jobs.snapshot(job_id)["result"], "recovered-after-worker-kill")
        self.assertIsNone(self.payloads.load(job_id))
        self.assertEqual(queue.leased_count(), 0)

    def test_flask_submission_and_separate_worker_process_share_real_job(self):
        context = multiprocessing.get_context("fork")
        output = context.Queue()
        web_process = context.Process(
            target=_run_flask_submission_process,
            args=(os.environ["JOB_STORE_REDIS_URL"], self.namespace, output),
        )
        web_process.start()
        status_code, response = output.get(timeout=20)
        web_process.join(timeout=20)
        self.assertEqual(web_process.exitcode, 0)
        web_process.close()
        output.close()
        output.join_thread()
        self.assertEqual(status_code, 202)
        job_id = response["job_id"]

        from atelier_engine.job_store import RedisJobStore
        shared_jobs = RedisJobStore(
            self.client, namespace=self.namespace + ":jobs", max_active=2
        )
        self.assertEqual(shared_jobs.snapshot(job_id)["status"], "running")
        saved = self.payloads.load(job_id)
        self.assertEqual(saved["handler"], "run_vision_lab_job")
        self.assertEqual(saved["args"][0], job_id)

        worker_output = context.Queue()
        worker_process = context.Process(
            target=_run_flask_worker_process,
            args=(os.environ["JOB_STORE_REDIS_URL"], self.namespace, job_id, worker_output),
        )
        worker_process.start()
        self.assertTrue(worker_output.get(timeout=20))
        worker_process.join(timeout=20)
        self.assertEqual(worker_process.exitcode, 0)
        worker_process.close()
        worker_output.close()
        worker_output.join_thread()
        completed = shared_jobs.snapshot(job_id)
        self.assertEqual(completed["status"], "done")
        self.assertEqual(completed["prompt"], "completed across processes")
        self.assertIsNone(self.payloads.load(job_id))
        self.assertEqual(self.queue.leased_count(), 0)

        poll_output = context.Queue()
        poll_process = context.Process(
            target=_poll_flask_job_process,
            args=(
                os.environ["JOB_STORE_REDIS_URL"], self.namespace, job_id,
                response["access_token"], poll_output,
            ),
        )
        poll_process.start()
        poll_status, poll_result = poll_output.get(timeout=20)
        poll_process.join(timeout=20)
        self.assertEqual(poll_process.exitcode, 0)
        poll_process.close()
        poll_output.close()
        poll_output.join_thread()
        self.assertEqual(poll_status, 200)
        self.assertEqual(poll_result["status"], "done")
        self.assertEqual(poll_result["prompt"], "completed across processes")
        self.assertNotIn("access_token", poll_result)

    def test_separate_worker_process_executes_persisted_job(self):
        job_id = uuid.uuid4().hex
        from atelier_engine.job_store import RedisJobStore
        shared_jobs = RedisJobStore(
            self.client, namespace=self.namespace + ":jobs", max_active=2
        )
        shared_jobs.create(job_id, {"status": "running", "created": time.time()})
        self.payloads.save(job_id, {
            "handler": "complete", "args": [job_id],
        })
        self.queue.enqueue(job_id, available_at=time.time())

        # CI runs on Linux; fork keeps the test helper isolated without
        # re-running unittest discovery in a spawned interpreter.
        context = multiprocessing.get_context("fork")
        result_queue = context.Queue()
        process = context.Process(
            target=_run_worker_process,
            args=(os.environ["JOB_STORE_REDIS_URL"], self.namespace, result_queue),
        )
        process.start()
        processed = result_queue.get(timeout=20)
        process.join(timeout=20)
        self.assertEqual(process.exitcode, 0)
        process.close()
        result_queue.close()
        result_queue.join_thread()
        self.assertTrue(processed)

        # Read through an independent Redis-backed store to verify shared state.
        self.assertEqual(
            shared_jobs.snapshot(job_id)["result"], "completed-in-child-process"
        )
        self.assertEqual(self.queue.leased_count(), 0)
        self.assertIsNone(self.payloads.load(job_id))

    def test_real_redis_queue_payload_and_worker_complete_end_to_end(self):
        self.jobs.create(self.job_id, {"status": "running", "created": time.time()})
        self.payloads.save(self.job_id, {
            "handler": "echo",
            "args": [self.job_id, {"binary": b"reference-image", "mode": "balanced"}],
        })
        self.queue.enqueue(self.job_id, available_at=time.time())

        def echo(job_id, payload):
            self.assertEqual(job_id, self.job_id)
            self.assertEqual(payload["binary"], b"reference-image")
            self.assertTrue(self.jobs.update_running(
                job_id, {"status": "done", "result": payload["mode"]},
                finished_at=time.time(),
            ))

        worker = RedisJobWorker(
            self.queue, self.payloads, self.jobs, {"echo": echo},
            heartbeat_interval_seconds=1,
        )
        self.assertTrue(worker.run_once())
        result = self.jobs.snapshot(self.job_id)
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["result"], "balanced")
        self.assertEqual(self.queue.pending_count(), 0)
        self.assertEqual(self.queue.leased_count(), 0)
        self.assertEqual(self.queue.dead_count(), 0)
        self.assertIsNone(self.payloads.load(self.job_id))


if __name__ == "__main__":
    unittest.main()
