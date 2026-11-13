# Redis worker operations runbook

This runbook applies only when the Redis-backed queue has been enabled in a controlled non-production environment. It is not approval to enable the queue in production.

## Before enabling the worker

- Use a dedicated Redis database/namespace for job state and a separate authenticated TLS Redis URL for rate limiting.
- Set `APP_ENV=production` only in a controlled environment that has the required authenticated `rediss://` rate-limit URL.
- Set `JOB_QUEUE_ENABLED=true` and `JOB_STORE_REDIS_URL` to the authenticated TLS URL supplied by the Redis provider.
- Keep provider credentials in the hosting platform's secret manager. Never paste them into logs, tickets, commits, or this runbook.
- Start the web service and the dedicated worker as separate supervised processes. The worker command is `python worker.py`.
- Use a process supervisor/container orchestrator with automatic restart on non-zero exit, bounded restart backoff, and an explicit stop timeout. Do not run the worker as an unsupervised shell process.
- Confirm that the web and worker services use the same queue namespace, Redis database, and compatible application release.

## Signals to monitor

Collect these signals from Redis and the worker process; do not expose job payloads, bearer tokens, Redis URLs, or provider credentials in telemetry.

| Signal | Healthy expectation | Investigate when |
| --- | --- | --- |
| Worker process | Exactly the intended supervised replica count is running | Process exits, repeatedly restarts, or replica count is zero |
| Redis connectivity | Worker can ping Redis and complete queue operations | Connection/authentication/TLS errors appear |
| Pending jobs | Returns toward zero after submissions stop | Oldest pending job age or queue depth grows continuously |
| Leased jobs | Usually reflects active work and falls after completion | Leases remain stuck beyond the configured lease/recovery window |
| Dead-letter jobs | Zero during normal operation | Count increases; inspect sanitized failure categories and retry patterns |
| Job outcomes | Jobs reach completed or error terminal states | Jobs remain running beyond their expected execution window |
| Worker logs | Startup, stop, retry, heartbeat and unexpected failures are visible | Heartbeat failures or repeated loop errors appear |

The queue exposes `pending_count()`, `leased_count()`, `dead_count()`, and `ping()` on its Redis queue object. These are operational signals, not a built-in HTTP health endpoint or monitoring dashboard. Instrument them through the deployment's trusted monitoring process without adding a public unauthenticated endpoint.

## Recovery procedure

1. Check the web service, worker supervisor, Redis availability, TLS/authentication, and recent deploy/configuration changes.
2. If the worker is down, inspect sanitized logs and Redis connectivity first. Restart it through the supervisor; do not manually delete queue keys.
3. Expired leases are recovered by the queue runtime. A restarted worker can reclaim eligible work; the queue enforces lease tokens so an expired worker cannot acknowledge a newer lease.
4. Watch pending, leased, and dead-letter counts while a small controlled test job completes.
5. Jobs moved to the dead-letter queue after repeated failures are surfaced as terminal errors by the worker. Diagnose the underlying cause before asking users to retry.
6. Never clear Redis databases or queue namespaces as a routine recovery action. Preserve evidence and job state until the incident is understood.

## Rollback / disable procedure

1. Stop accepting new background work by disabling queue mode in the controlled environment and redeploying the known-good web configuration.
2. Stop the worker gracefully through the supervisor (SIGTERM/SIGINT); the worker stops after its current processing path and queue leases provide recovery protection if a process is terminated unexpectedly.
3. Confirm the web service is healthy in the supported non-queue mode and that no new jobs are being enqueued.
4. Preserve Redis state and sanitized logs for investigation. Do not delete pending/leased/dead-letter data unless an approved recovery plan explicitly calls for it.
5. If reverting an application release, keep the Redis schema/namespace compatibility in view. Do not roll back only one service if web and worker versions would become incompatible.

## Acceptance checklist for a controlled test deployment

- [ ] Authenticated TLS Redis connectivity succeeds from both web and worker services.
- [ ] Web service starts with the intended production-like configuration and refuses unsafe rate-limit storage settings.
- [ ] Worker starts under supervision and reports a stable running process.
- [ ] A harmless test job is submitted, claimed, completed, and polled to a terminal state.
- [ ] Worker termination during a test job is followed by lease expiry/recovery and a successful retry or a clear terminal error.
- [ ] Repeated failures reach the dead-letter path and are visible as a terminal error.
- [ ] Pending, leased, and dead-letter signals are observable without exposing secrets or job payloads.
- [ ] Rollback to non-queue mode is exercised and verified.
- [ ] An operator records the test date, application commit, Redis provider/configuration class (no credentials), outcomes, and rollback result.

Production queue enablement remains blocked until every acceptance item has been exercised in a controlled environment and an operator has approved monitoring, recovery, and rollback.
