# Shared job storage architecture decision

**Status:** Opt-in Redis queue integration and multi-process CI acceptance tests implemented; production enablement remains pending  
**Scope:** Generation, optimization, scratch synthesis, and Vision Lab background jobs

## Current constraint

By default, local development and tests still use the process-local in-memory job store and daemon threads. When `JOB_QUEUE_ENABLED=true` and a reachable `JOB_STORE_REDIS_URL` are explicitly configured, the Flask app uses Redis job records and durable queue submission, and a separate `worker.py` process executes the allowlisted handlers. The CI suite now exercises real Redis with separate Flask submission, worker execution, and status-polling processes; it also kills a running worker and verifies lease-based recovery after restart. Atomic lease fencing and bounded recovery batches are covered. These tests validate the integration contract, but do not replace a controlled test-environment deployment and operational review. Keep production on its existing single-worker configuration and leave queue mode disabled.

## Target design

1. **Redis job records:** Store each job under a versioned key such as `atelier:jobs:v1:<job_id>`. Serialize only JSON-compatible job metadata and results. Never store reference image bytes, provider credentials, or raw authorization headers in job records. Store binary request inputs separately under expiring payload keys; queue messages should contain only a job ID. The payload serializer preserves bytes and tuples without using pickle and enforces a size ceiling.
2. **Atomic capacity reservation:** Use a Redis Lua script to check the global active-job count and reserve a new job in one operation. This prevents concurrent web processes from exceeding the configured active-job cap.
3. **Active and finished indexes:** Maintain sorted sets for active job IDs and terminal job IDs. A terminal status update removes the job from the active set and adds it to the finished-history index atomically with the record update.
4. **Bounded retention:** Apply a configurable TTL to job records and prune the oldest finished IDs from the finished-history index. Running jobs must never be evicted merely to satisfy finished-history retention.
5. **Status isolation:** Preserve the existing random per-job bearer token, constant-time comparison, UUID-hex ID validation, response allowlist, and `no-store` headers. Do not return the stored token in status payloads.
6. **Configuration:** Use a dedicated `JOB_STORE_REDIS_URL`, separate from `RATELIMIT_STORAGE_URI`. Validate connectivity at startup when configured. In production, do not silently fall back to process-local storage if shared storage was explicitly requested but unavailable.

## Worker execution and restart safety

A Redis-backed status store and payload store alone do not make daemon-thread execution durable. Job payloads can include reference-image bytes (up to the request size limit), so the durable queue must reference a separately stored, expiring payload rather than embedding image data in queue metadata. A Redis queue implementation provides atomic enqueue/claim, per-worker lease tokens, heartbeat extension, atomic job-store lease fencing, bounded retries, dead-letter handling, and batched expired-lease recovery. Worker heartbeats also refresh the job-store liveness index so abandoned pre-enqueue records and inactive jobs eventually become terminal without timing out healthy long-running jobs. When explicitly enabled, HTTP submission stores the handler name and arguments in the expiring payload store and enqueues only the job ID. A separate `worker.py` process loads the payload and runs an allowlisted handler. Real-Redis CI tests cover Flask submission in one process, worker execution in another, authenticated polling from an independent Flask process, concurrent web-process capacity, worker termination, and restart recovery. Redis must be private, authenticated, and configured with appropriate persistence and transport security before it holds these inputs. Execution is at-least-once: if a process stops after a provider call succeeds but before committing its result, a retry can repeat the call. Keep the queue opt-in until a controlled test-environment deployment and operational review are complete.

## Migration sequence

- Add a small job-store interface matching the current operations: create, update, snapshot, token lookup, delete, and retention.
- Keep the in-memory implementation for isolated unit tests and explicitly single-worker development.
- [x] Add an expiring Redis payload store with a bounded, non-pickle serializer for bytes, tuples, and JSON metadata.
- [x] Add a Redis adapter with Lua-atomic capacity reservation, active/finished indexes, terminal transitions, and record TTL. Contract tests cover serialization/configuration guards.
- [x] Add fake-client behavioural tests and real Redis Lua integration tests in CI before enabling it in deployments.
- [x] Migrate all direct `jobs` dictionary access to the interface.
- [x] Add atomic capacity, TTL, active/finished-index, terminal-state, and stale-job maintenance tests.
- [x] Implement a Redis queue primitive with atomic enqueue/claim, lease-token heartbeats, atomic job-store lease fencing, retry limits, dead-letter handling, and bounded expired-lease recovery; fake-client and real-Redis tests added.
- [x] Add opt-in Flask submission integration that stores request arguments separately and enqueues only the job ID.
- [x] Add a dedicated `worker.py` process entrypoint with allowlisted handlers, heartbeat renewal, retry/backoff, terminal-state handling, stale-lease fencing, and dead-letter finalization.
- [x] Tie worker heartbeat activity to the job-store liveness index; Redis stale-job expiry now uses heartbeat timestamps rather than job creation time.
- [x] Verify Flask job creation, authenticated polling, worker execution, and worker-kill/restart recovery across separate processes against real Redis in CI.
- Only then remove the single-Gunicorn-worker restriction.

## Opt-in worker configuration (not production-approved yet)

The queue provides **at-least-once** execution, not exactly-once execution. If a worker crashes after a model-provider request succeeds but before the job result is committed, a retry can repeat that provider request and its cost. Keep handlers safe against duplicate execution; do not assume an interrupted provider call was never processed.

For a test environment only, configure the same values for the web service and worker service:

- `JOB_QUEUE_ENABLED=true`
- `JOB_STORE_REDIS_URL=<private Redis connection URL>`
- Production queue mode requires an authenticated `rediss://` URL (TLS plus a password); startup rejects plaintext or unauthenticated Redis configuration. Redis connect/read timeouts are bounded so an unavailable service fails startup instead of hanging indefinitely.
- Optional shared namespace/TTL settings: `JOB_STORE_NAMESPACE`, `JOB_PAYLOAD_NAMESPACE`, `JOB_QUEUE_NAMESPACE`, `JOB_RECORD_TTL_SECONDS`, `JOB_PAYLOAD_TTL_SECONDS`, `JOB_QUEUE_LEASE_SECONDS`, `JOB_QUEUE_MAX_ATTEMPTS`, `JOB_QUEUE_COMPLETED_TTL_SECONDS`, and `JOB_QUEUE_RECOVERY_BATCH_SIZE` (maximum expired leases recovered per worker poll).
- Optional worker tuning: `JOB_WORKER_HEARTBEAT_SECONDS` (must remain below half the lease), `JOB_WORKER_RETRY_BACKOFF_SECONDS`, `JOB_WORKER_POLL_SECONDS`, and `WORKER_LOG_LEVEL`.
- Start the web service using its existing command and start a separate worker service with `python worker.py`.
- The worker service also needs the same model-provider credentials and model configuration required by the web app.

If queue mode is enabled without a Redis URL or Redis is unreachable, app startup fails rather than falling back to in-memory jobs. The automated multi-process, worker-kill, restart, and end-to-end polling checks are covered in CI. Keep queue mode disabled in production until a separate test-environment deployment, Redis persistence/security review, provider-credential setup, and operational monitoring are verified.

## Acceptance criteria

- Two independent web processes can create and poll the same job.
- Concurrent job creation cannot exceed the global active-job limit.
- A job token is never exposed in logs, status JSON, or job metadata returned to clients.
- Production queue startup rejects plaintext or unauthenticated Redis URLs and fails visibly when Redis cannot be reached.
- Finished jobs expire according to policy; active jobs are protected from ordinary history pruning.
- Worker restart and provider failure have explicit, tested terminal/retry behavior.
- Production configuration fails visibly rather than silently degrading to local-only job state.
