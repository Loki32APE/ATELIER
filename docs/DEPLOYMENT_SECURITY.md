# Deployment security and reliability

## Required production configuration

Set these environment variables in the hosting provider's **Environment** settings:

- `APP_ENV=production`
- `RATELIMIT_STORAGE_URI=rediss://default:<REDIS_PASSWORD>@<REDIS_HOST>:<REDIS_PORT>/0`

If and only if the durable queue has passed a controlled test-environment deployment and operations review, also configure:

- `JOB_QUEUE_ENABLED=true`
- `JOB_STORE_REDIS_URL=rediss://default:<REDIS_PASSWORD>@<REDIS_HOST>:<REDIS_PORT>/1`
- A separately supervised worker service running `python worker.py`, with the same Redis URL/namespaces and model-provider credentials as the web service.

Production queue mode rejects plaintext `redis://` URLs and URLs without a password. Redis connect/read timeouts are bounded. Keep `JOB_STORE_REDIS_URL` separate from `RATELIMIT_STORAGE_URI`; they serve different application responsibilities.

Use the TLS connection URL supplied by your Redis provider. Keep the password in the hosting provider's secret/environment settings; never commit real credentials to Git.

For deployments behind a reverse proxy, set `TRUSTED_PROXY_HOPS` to the exact number of trusted proxies that overwrite and sanitize `X-Forwarded-For` (commonly `1`). It defaults to `0`, so forwarded headers are not trusted by default. Never enable it if clients can supply their own forwarded headers through the trusted proxy.

## Reproducible Python dependency installation

- `requirements.in` is the source manifest for direct application dependencies.
- `requirements.lock` is the generated, fully pinned application dependency set with package hashes. Use `python -m pip install --require-hashes -r requirements.lock` for controlled deployments.
- `requirements-test.in` and `requirements-test.lock` add browser-test dependencies; CI installs the test lock with hash verification.
- Do not edit generated lockfiles by hand. The dependency-lock workflow compiles and verifies them, then updates the dependency-lock pull request for review.

Flask-Limiter uses the configured Redis store to share rate-limit counters across application processes. Production startup fails closed unless this variable is an authenticated, TLS-protected `rediss://` URL; it will not silently run with process-local `memory://` rate limits.

## Important worker limitation

The default development/test mode still uses an in-memory job store and daemon threads. An opt-in Redis job store, expiring payload store, leased queue, and separate `worker.py` process are implemented and covered by real-Redis multi-process CI tests, including Flask submission, authenticated polling, worker termination, and restart recovery. However, CI coverage is not a production rollout approval. Keep production on its existing **one Gunicorn worker** configuration and leave `JOB_QUEUE_ENABLED` disabled until a controlled test deployment, Redis persistence/security review, provider-credential setup, monitoring, and rollback plan are complete. Redis-backed rate limiting alone does not make job state shared; the job queue must be explicitly enabled and a worker service must be running.

## Historical credential exposure review

A repository-history review found that a root `.env` file existed in an earlier commit and was later deleted. The file is absent from the current `main` and `visual-lab-rebuild` trees, and the current `.gitignore` excludes `.env` and `.env.*` while allowing the safe `.env.example` template.

Deleting the file does not remove its contents from prior Git commits. The repository owner has reported that the exposed key was revoked; that provider-side revocation cannot be independently verified from GitHub repository access. Treat every value that was ever stored in that historical file as compromised until its provider confirms revocation or rotation. Review provider audit logs and rotate any other credentials that may have been present.

Git history rewriting was intentionally not performed. It changes commit IDs and can disrupt collaborators, open pull requests, deployments, and clones; perform it only as a separately approved, coordinated operation after credential revocation.

## Existing safety defaults

- Telegram webhook is disabled unless explicitly enabled with its required token and secret.
- Telegram webhook updates are restricted to the development repository and `visual-lab-rebuild`; production repository/`main` targets are blocked.
- Telegram file-edit commands accept only normalized repository-relative paths; absolute paths, traversal segments, control characters, and Git metadata paths are rejected.
- Telegram reply transport failures are logged without exception details because request URLs contain the bot token.
- Job status polling requires the per-job bearer token returned when a job is created.
- Unknown job IDs and unauthorized job IDs intentionally return the same status and message to reduce job-existence disclosure.
- Vision Lab rejects non-finite numeric values (NaN and positive/negative infinity) in nested selection data; JSON numbers must be finite.
- Configure `MAX_ACTIVE_JOBS` for the expected workload; values are clamped to 1–16 and invalid values fall back to 4. Its limit is per process in in-memory mode and globally reserved in Redis queue mode.

## Application response protections

- All responses include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, a restrictive `Referrer-Policy`, and a `Permissions-Policy` disabling camera, microphone, and geolocation access.
- Background generation failures return generic client-safe messages; detailed unexpected exceptions are written to server logs rather than exposed through job polling.
- The text-only Vision Lab validation endpoint is rate-limited to 30 requests per minute per client address. AI-backed endpoints have their own lower limits.
- Reference uploads are checked against their declared MIME type, actual decoded image format, image integrity, byte limits, and a 40-million-pixel ceiling before being forwarded.

- Rate-limit client identity uses the direct remote address by default. Forwarded IP headers are only trusted when `TRUSTED_PROXY_HOPS` is explicitly configured for a correctly configured proxy chain.

- Job-status polling is limited to 180 requests per minute per client address; this leaves headroom for normal polling from multiple concurrent browser jobs while bounding excessive polling.
- Oversized requests (HTTP 413) and rate-limit responses (HTTP 429) return structured JSON errors for the browser clients.
- Vision Studio's file picker and client-side checks accept JPEG, PNG, and WebP up to 4 MB per reference; server-side decoding and size checks remain authoritative.
- Telegram webhook messages are capped at 4,096 characters and chat IDs must be numeric before any repository operation or reply is attempted.

- Telegram webhook processing failures are logged with a generic message; third-party exception details are not written to logs.

- OpenRouter transport exceptions are replaced with a generic retry-safe message; raw request exception details are not returned to clients.

## Authentication, browser origins, and error handling audit

- The current Flask application does not configure a cookie-backed login/session flow or emit a session cookie on the home response. No cookie-authenticated state-changing route was identified in this audit; revisit CSRF controls if such a flow is introduced.
- The application does not emit `Access-Control-Allow-Origin`; no permissive CORS policy is configured by the inspected app code. Keep cross-origin access disabled unless a specific trusted frontend origin is required.
- Unhandled HTTP 500 errors now return a generic JSON message. Exception details remain out of client responses; the standard Flask server-side error logging remains available for diagnosis.
