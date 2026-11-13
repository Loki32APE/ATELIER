"""Dedicated Redis queue worker entrypoint.

Run separately from the Flask web process with JOB_QUEUE_ENABLED=true and the
same JOB_STORE_REDIS_URL/namespaces. Example: python worker.py
"""
import logging
import os
import signal

from app import (
    JOB_QUEUE_ENABLED,
    app,
    job_payload_store,
    job_queue,
    job_store,
    run_generate_job,
    run_optimize_job,
    run_scratch_job,
    run_vision_lab_job,
)
from atelier_engine.worker_runtime import RedisJobWorker


def main():
    if not JOB_QUEUE_ENABLED or job_queue is None or job_payload_store is None:
        raise RuntimeError(
            "The dedicated worker requires JOB_QUEUE_ENABLED=true and a reachable JOB_STORE_REDIS_URL."
        )

    logging.basicConfig(
        level=os.environ.get("WORKER_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    handlers = {
        "run_generate_job": run_generate_job,
        "run_optimize_job": run_optimize_job,
        "run_scratch_job": run_scratch_job,
        "run_vision_lab_job": run_vision_lab_job,
    }
    worker = RedisJobWorker(
        job_queue,
        job_payload_store,
        job_store,
        handlers,
        heartbeat_interval_seconds=(
            float(os.environ["JOB_WORKER_HEARTBEAT_SECONDS"])
            if os.environ.get("JOB_WORKER_HEARTBEAT_SECONDS") else None
        ),
        retry_backoff_seconds=int(os.environ.get("JOB_WORKER_RETRY_BACKOFF_SECONDS", "5")),
        poll_interval_seconds=float(os.environ.get("JOB_WORKER_POLL_SECONDS", "1")),
        logger=app.logger,
    )
    app.logger.info("Atelier Redis worker started with %d handlers", len(handlers))

    def request_stop(signum, _frame):
        app.logger.info("Atelier Redis worker received signal %s; stopping after current job", signum)
        worker.stop()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    worker.run_forever()


if __name__ == "__main__":
    main()
