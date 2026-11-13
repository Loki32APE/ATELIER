# Security Requirements & Guardrails

## 1. Secrets and Environment Variables
- Never commit real API keys, tokens, or credentials (`OPENROUTER_API_KEY`, `GITHUB_TOKEN`, `TELEGRAM_TOKEN`, `OWNER_TELEGRAM_ID`) in source code, frontend JavaScript, or new Git commits.
- Provider calls must run server-side. The browser must never receive raw API keys.
- Commit only a safe `.env.example` containing blank placeholders or clearly fake examples.
- Deleting a secret from the latest tree does not remove it from Git history. Treat historical credentials as compromised and verify provider-side revocation/rotation.

## 2. Vision Studio Upload Security
- Do not trust client-supplied MIME types or extensions. Verify binary magic bytes for JPEG, PNG, and WebP.
- Use bounded stream reads and reject oversized files before allocating full payloads.
- Enforce the configured per-file, aggregate request-size, and reference-count caps.
- Sanitize filenames, remove path traversal and control characters, and never use user filenames as filesystem paths.

## 3. Workspace Boundaries and Input Validation
- Visual Lab is text-only. Reject image uploads and image-reference metadata at the backend boundary.
- Vision Studio is the only workspace that accepts Look and Outfit references.
- Enforce request-size, character-length, JSON-depth, known-module, detail-level, and target-model constraints.
- Reject malformed or unsupported requests with safe 4xx responses.

## 4. Rate Limits and Error Handling
- Protect expensive generation, optimization, and synthesis endpoints with rate limits.
- Return structured, user-safe error messages. Never expose stack traces, secrets, environment values, or server paths.
- Log diagnostic details server-side with secrets redacted.

## 5. Queue and Worker Safety
- Redis-backed queue is opt-in and must remain disabled in production until controlled staging acceptance.
- Production queue mode requires authenticated TLS Redis, a supervised worker, monitoring, and a documented rollback.
- Queue payload bytes and job metadata remain separate; enforce lease ownership and bounded recovery.
- Do not change production worker or Redis settings as part of ordinary development.

## 6. Legacy Integrations
- Keep legacy Telegram/GitHub self-modifying webhooks disabled by default unless explicitly authenticated and enabled through environment flags.
