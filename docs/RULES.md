# AI Development Rules

## 1. General Principles
- Keep business logic, validation, and AI orchestration in focused `atelier_engine/` modules. Keep Flask routes thin.
- Reuse shared schemas and the unified Catalog Service. Never create duplicate global JavaScript functions.
- Keep functions small, deterministic where possible, and independently testable.
- Touch only files required by the active task in `TASKS.md`. Do not alter unrelated files or production configuration.

## 2. Mandatory Read-First Procedure
Before coding:
1. Read `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/DECISIONS.md`, `docs/MEMORY.md`, and `TASKS.md`.
2. Inspect the current implementation and tests; do not assume a task is still outstanding until verified.
3. Confirm Visual Lab is text-only and Vision Studio exclusively owns reference-image workflows.
4. Write a short plan and identify regression risks before editing.

## 3. Frontend Rules
- Follow the approved dual-mode tokens in `static/css/brand-tokens.css` and the attached production assets pack.
- Support desktop multi-panel, tablet adaptive, and mobile touch-first layouts through viewport breakpoints; do not add separate preview toggles.
- Use semantic controls, visible keyboard focus, accessible names, and keyboard activation.
- Implement Loading, Empty, Partial/Conflict, Error, and Success states for asynchronous flows.
- Never overwrite a manually edited prompt without explicit user confirmation.

## 4. Backend & Intelligence Rules
- Explicit user instructions and selections must never be silently dropped or contradicted.
- Repair is non-destructive: return a separate repair candidate while preserving the original prompt.
- Keep reasoning-provider choice separate from target image-model formatting.
- Bound payload sizes, omit empty values, deduplicate repeated tags, and handle partial provider failures safely.
- Use exact case-sensitive static paths, especially `/static/Catalog/`.

## 5. Security Rules
- Never hardcode or expose API keys, tokens, or credentials. Read secrets only from server-side environment variables.
- Validate uploaded image magic bytes; sanitize filenames; enforce per-file, aggregate-size, and file-count limits before reading full payloads.
- Return sanitized client errors; log diagnostics securely without exposing stack traces, secrets, or server paths.
- Keep legacy webhooks disabled unless explicitly authenticated and enabled.

## 6. Testing & Git Workflow
- Every backend behavior change requires unit/integration tests. User-visible changes require browser coverage.
- Run Python tests, JavaScript syntax checks, browser tests, and relevant security/dependency audits before committing.
- Follow the loop: READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCS.
- Develop only on `visual-lab-rebuild`. Never modify/deploy production without explicit approval.
- Use descriptive, atomic commits and update `TASKS.md` and `docs/MEMORY.md` with verified outcomes only.
