# System Architecture

## 1. High-Level Overview
Atelier Prompt Engine is a modular full-stack Python web application built on Flask, with OpenRouter AI integration and a dual-mode frontend following the approved Darkroom Obsidian & Warm Archival Paper asset pack. It separates shared platform services from two independent creative workspaces: **Visual Lab** (the user-facing name; internal backend identifiers retain `vision_lab` for compatibility) and **Vision Studio**. A future combined Vision Engine is reserved and is not part of the current build.

```text
USER (Desktop / Mobile)
        |
        v
FRONTEND (HTML5 / CSS3 / Modular JavaScript)
  | Visual Lab | Vision Studio | Library | Settings |
        |
        v
FLASK API GATEWAY (app.py)
  authentication / rate limits / validation / uploads / jobs
        |
        v
ATELIER ENGINE (atelier_engine/)
  schemas & boundaries
  deterministic rules
  AI composition and Studio synthesis
  model capability profiles and optimizers
  quality validation and non-destructive repair
        |
        v
OPENROUTER (reasoning provider)
        |
        v
TARGET IMAGE MODEL OPTIMIZATION (separate from reasoning provider)
```

## 2. Technology Stack
- Backend: Python 3.11+, Flask, Gunicorn.
- AI reasoning: OpenRouter; provider/model selection remains server-side.
- Frontend: semantic HTML, CSS design tokens, modular vanilla ES modules / JavaScript.
- Storage: browser storage for local preferences and temporary history; durable saved prompts and profiles require a versioned storage adapter and explicit user save actions.
- Tests: Python unittest, JavaScript syntax validation, Playwright browser tests, dependency/security audits.
- Deployment: development on `visual-lab-rebuild`; production is a separate, explicitly approved release activity.

## 3. Architectural Layers

### A. Frontend shell
- One application shell owns navigation, workspace switching, responsive layout, notifications, and global state.
- Workspace-specific UI remains isolated: Visual Lab, Vision Studio, Library, and Settings.
- Use semantic controls and accessible keyboard behavior.
- User-facing product name is **Visual Lab**. Existing API routes, Python modules, and persisted keys named `vision_lab` or `scratch` are internal compatibility identifiers and must not be renamed without migration tests.

### B. Shared platform services
- `core.js`: shared state, notifications, storage adapters, navigation, and desktop/mobile view preference.
- `catalog-service.js`: the only browser service allowed to load catalog JSON; it reads from the exact `/static/Catalog/` path and provides caching, validation, error states, and typed accessors.
- Storage adapters: versioned schemas, migration, export/import validation, and explicit save semantics.
- API client: centralized request handling, timeout/error normalization, and safe response parsing.

### C. Visual Lab workspace
- Strictly text-only; no image reference upload or reference metadata.
- Seven modules: Appearance & Identity; Outfit & Styling; Poses & Expressions; Themes & Environment; Lighting & Composition; Camera & Photography; Output & Rendering Intelligence.
- Basic mode provides guided, beginner-friendly controls.
- Advanced mode provides granular controls and custom overrides.
- A shared state model feeds the structured prompt pipeline.
- Generated prompts support Copy and Edit. Edits are revalidated.
- Compatibility suggestions are advisory; they never silently change a selection.

### D. Vision Studio workspace
- Separate Look Reference and Outfit Reference scopes.
- Look analysis covers pose, framing, gaze, lighting, environment, and visible range; it must not replace identity.
- Outfit analysis covers garment construction, fabric, embroidery, folds, jewellery, and footwear.
- Fast, Balanced, and Detailed processing modes.
- Independent analysis status and failure recovery.
- Master and RAW outputs remain separate contracts.
- Explicit user overrides have priority over reference inference.

### E. Backend intelligence pipeline
```text
Input Collection
  -> Schema Validation & Normalization
  -> Deterministic Rules / Conflict Detection
  -> Structured Handoff
  -> AI Composer or Studio Synthesizer
  -> Target-Model Optimizer
  -> Quality Validator
  -> Original + Optional Repair Candidate
```
- Explicit user instructions are never silently removed.
- Reasoning provider and target image model are separate concepts.
- Repair returns a separate candidate; original output remains intact.
- Quality scoring dimensions: completeness 25%, consistency 25%, instruction preservation 20%, model compatibility 20%, clarity 10%.

### F. Backend reliability
- Flask routes remain thin and delegate to `atelier_engine/`.
- Upload validation uses magic bytes, bounded reads, file-count and aggregate-size caps.
- Job state and payload storage are separated.
- Redis-backed queue is opt-in; production queue activation requires a controlled staging test, authenticated TLS Redis, a supervised worker, monitoring, and a rollback plan.
- Never paste secrets into source code or commit real `.env` files.

## 4. Data Flow and Boundaries
1. The UI collects user selections and sends a schema-valid request.
2. Backend validation checks workspace identity and rejects invalid fields.
3. Visual Lab requests are text-only. Vision Studio requests pass the upload security boundary.
4. Deterministic rules detect conflicts and preserve explicit user instructions.
5. AI composition/synthesis is called with a bounded, structured payload.
6. Target-model optimization formats the result for the selected image model.
7. Quality validation returns scores, warnings, original output, and (if needed) a separate repair proposal.
8. Only an explicit Save action writes to the permanent Library. Temporary generations stay in bounded session history.

## 5. Core Architectural Rules
1. Keep Visual Lab and Vision Studio separate at both UI and backend validation layers.
2. Use one catalog-loading service; no direct catalog fetches from individual modules.
3. Use exact uppercase `/static/Catalog/` paths for Linux deployment compatibility.
4. Do not create duplicate global JavaScript functions. Prefer module scope and explicit exports.
5. Preserve existing API contracts and storage keys unless a migration is included and tested.
6. Never silently overwrite prompts, user choices, or saved versions.
7. Keep the target image model independent from the AI reasoning provider.
8. Implement Loading, Empty, Partial/Conflict, and Error states for asynchronous flows.
9. Add tests for every backend behavior change and browser coverage for user-visible changes.
10. Develop only on `visual-lab-rebuild`; production release requires separate explicit approval.
