# Atelier Prompt Engine — Current Project Memory

## Project and repository
- Product: Atelier Prompt Engine — "Where Imagination Meets Intelligence."
- Development repository: `LokeshofficialGit/ATELIER_PROMPT_ENG.`
- Active development branch: `visual-lab-rebuild`.
- Production repository/service is separate. Do not modify or deploy production without explicit user approval.
- User-facing workspace name: **Visual Lab**. Internal identifiers such as `vision_lab` and legacy `scratch` routes remain for compatibility until a tested migration is approved.

## Approved product boundaries
- Visual Lab: strictly text-only, seven modules, Basic and Advanced modes.
- Vision Studio: reference-based workflow with separate Look Reference and Outfit Reference, independent analysis, Master and RAW outputs, creative overrides, fabric physics, and review/retry.
- Vision Engine: future scope only; do not build during the current completion work.
- Library: My Projects, Prompt Library, Reference Library, Favorites, History, search, filters, bulk actions, and user-controlled saving/versioning.
- Settings: Profile & Account, Appearance, Workspace Preferences, Prompt Preferences, AI Configuration, Storage & Data, About Atelier.
- Design: Follow the approved Darkroom Obsidian & Warm Archival Paper production pack; keep its vermilion prism identity and specified fonts unchanged.

## Architecture principles
- Flask routes stay thin; core schemas, validation, intelligence, and orchestration live in `atelier_engine/`.
- One shared Catalog Service must load all JSON from exact `/static/Catalog/` paths.
- No duplicate global JavaScript functions.
- Reasoning provider is separate from target image model.
- User instructions and overrides are never silently dropped.
- Repair is non-destructive; original prompt remains available.
- Permanent saving is explicit; generated variants remain temporary until saved.
- Redis queue is opt-in and must remain disabled in production until controlled staging acceptance.

## Verified implementation
- Shared workspace schemas and validation.
- Vision Lab backend pipeline: seven-module registry, normalization, deterministic rules, structured payload, AI composer, model profiles, quality validation, and non-destructive repair.
- Vision Studio reference separation, independent failure recovery, coverage checks, conflict priority, RAW contract, and quality review.
- Upload magic-byte validation, bounded reads, rate limiting, sanitized errors.
- Redis queue/worker reliability implementation with multiprocess recovery tests; production activation is not approved.
- Dependency lockfiles, CI, dependency security audit, worker operations runbook, deployment security documentation.
- GitHub Actions run `43049213077` passed all four jobs: Python unit tests, Chromium desktop/mobile smoke tests, JavaScript syntax validation, and Python dependency audit.

## Latest development checkpoint (2026-11-11)
- Integrated the canonical PRD, architecture, design, rules, decisions, security, test plan, Cursor rules, task tracker, and safe `.env.example` into the development branch. The product-facing name is documented as **Visual Lab**; internal `vision_lab` identifiers remain compatible.
- Added the shared catalog service and migrated Theme/Jewellery catalog loading to it. Added a separate seven-module Visual Lab catalog with Basic and Advanced structured controls.
- Removed duplicate global function declarations across the active frontend JavaScript files; a repository-wide declaration scan found no remaining duplicate global declarations. Remaining same-named helpers are scoped inside IIFEs.
- Added unified Library sections for projects, prompts, references (IndexedDB), favorites, and history, with search, project assignment, bulk actions, comparison, and version saving.
- Added functional local Settings sections and the persistent Home Desktop/Mobile view switcher. API credentials remain server-side and are never stored in browser settings.
- Added source-contract and Playwright tests for catalog controls, mode persistence, Library workflows, local reference storage, Settings persistence, and view switching. GitHub Actions run #426 (43070212918) passed all four jobs on 2026-11-11, including Python tests, Chromium desktop/mobile smoke tests, JavaScript syntax, and dependency audit.

### Visual Lab audit update (2026-11-11)
- Fixed the empty Creative Profile selection edge case so Load cannot implicitly load the first saved profile and overwrite unsaved work.
- Added catalog schema coverage and a browser test exercising every Basic and Advanced catalog field across all seven modules, verifying the complete generation payload.
- Added advisory Outfit/Pose guidance for saree movement/seated drape, lehenga movement, and heels with movement. Guidance is informational and does not mutate selected values.
- Added backend regression tests and a browser test proving advisory guidance is displayed. CI run #414 (43068253874) passed all four jobs, including the full catalog-field browser test.
- Added AI-output selection coverage: if the reasoning model omits any chosen catalog value or protected instruction, the pipeline restores it verbatim in a labeled section, sets `needs_review`, and surfaces an optimization warning. Added pipeline tests for omission recovery across all seven modules, no-duplicate behavior, and real multiline provider context, plus a browser test for the review notice. CI run #426 (43070212918) passed all four jobs.
- TASK-017 is complete. TASK-016 remains in progress pending deeper field-by-field interaction and generated-prompt quality verification.

### Responsive UI update (2026-11-13)
- Removed the Home desktop/mobile preview controls and the saved preferred-view setting. Layout now follows the real viewport width; phone navigation uses the bottom bar.

## Remaining work
1. Complete: unified Catalog Service and safe catalog consumer migration (TASK-015; CI #459 passed).
2. Complete real-provider generated-prompt quality review and manual acceptance for the seven Visual Lab modules; all catalog fields in Basic and Advanced modes have browser payload coverage and AI omission recovery is tested.
3. Complete: outfit/pose compatibility suggestions (TASK-017).
4. Library, Settings, and Home desktop/mobile switcher are implemented and CI-verified; detailed manual acceptance remains.
5. Finish accessibility and consistent async UI-state audit.
6. Finish remaining browser regression cases listed in TASKS.md.
7. Run real-image Vision Studio benchmark.
8. Complete controlled staging tests for TLS Redis, worker recovery, monitoring, and rollback.
9. Production release remains blocked pending full QA and explicit user approval.

## Historical security note
A previous repository commit contained a root `.env` file. It was later deleted from the current tree, but deletion does not erase Git history. The owner has reported revocation of the exposed key; provider-side revocation cannot be independently verified through repository access. Treat all historical values as compromised until provider revocation/rotation is confirmed. Do not rewrite Git history without a separate coordinated approval.

## Latest verified checkpoint
- Branch: `visual-lab-rebuild`.
- Latest verified CI run before this documentation update: #459 (`43075808123`), all four jobs successful on commit `040565c3fdec856f23103ef32ba015471ad40764`.
- TASK-015 catalog service verification is complete: strict path/ID/schema validation, manifest integrity tests, shared cache safety, consumer script order, and no direct catalog JSON fetches found in active frontend JavaScript. Theme and Jewellery are migrated; Visual Lab consumes the shared service.
- TASK-016 remains open for real-provider prompt-quality/manual acceptance. Mocked and deterministic tests are not provider acceptance.
- TASK-018/019/020 implementation and CI checks are verified; detailed manual acceptance remains open. TASK-021/022 retain the audit/regression gaps recorded in TASKS.md.


## Latest Library CI verification (2026-11-12)
- Library tabs support Home and End keyboard navigation in addition to arrow keys; browser coverage restores the Prompt Library view before triggering Favorite.
- GitHub Actions run #533 (`43162564554`, commit `95da21f6f537b9245680bc4e44d4095edd691b88`) passed Python tests, Chromium desktop/mobile smoke tests, JavaScript syntax validation, and dependency audit.
- This workspace contains the code and browser-test changes for that run. Real-provider prompt-quality review, real-image benchmark, staging acceptance, complete manual acceptance, and historical provider-key revocation confirmation remain unverified.
- This documentation update will trigger a fresh CI run; do not treat it as verified until that run completes.
- A prior run `43033715975` failed before browser tests began because the hosted runner could not resolve Ubuntu package mirrors while installing Playwright OS dependencies; Python tests and JS syntax passed in that run. Treat this as a runner/network installation failure, not an application regression.
- Do not claim the full product or Phase release readiness is complete from CI alone.


## Phase B/C verification update (2026-11-12)
- Settings navigation regression verifies all seven sections, hidden/visible panel state, and exactly one current navigation item. CI #466 (`43152140769`) and #467 (`43152228736`) passed all four jobs.
- Settings reset coverage now includes cancellation (data preserved) and confirmation (all currently known local-storage keys and the `AtelierLibraryDB` IndexedDB database removed). CI #468 (`43152871072`) passed all four jobs.
- Vision Studio Look/Outfit inspect and remove icon buttons have explicit accessible names. CI #469 (`43152882048`) passed all four jobs.
- Active frontend storage audit confirms Settings reset covers all currently known application local-storage keys and the Reference Library database.
- Remaining: wider semantic and asynchronous-state accessibility review; detailed manual acceptance; real-provider Visual Lab prompt-quality review; real-image Vision Studio benchmark; controlled staging acceptance; final security review. Production release remains blocked and requires explicit user approval.


## Accessibility and regression update (2026-11-12)
- The minimized prompt output dock is now exposed as a keyboard-focusable button and responds to Enter; its browser regression test verifies dock dismissal and output expansion.
- CI #472 (`43153631455`), #473 (`43153642958`), and #474 (`43153658239`) all passed Python tests, Chromium desktop/mobile smoke tests, JavaScript syntax, and dependency audit.
- The existing Studio regression suite covers reference removal, analysis retry, and optimize success/failure. Settings reset cancel and confirmed paths are both browser-tested.
- TASK-021/022 remain in progress for the wider semantic/async-state review and detailed manual acceptance. Real-provider, real-image, staging, and release gates remain open.


## Output accessibility and preliminary security reconnaissance (2026-11-12)
- Converted the output sheet minimize handle to a native labeled button and added browser coverage for its minimize action. The minimized dock keyboard-open path remains covered.
- CI #475–#479 passed all four jobs (Python tests, Chromium desktop/mobile, JavaScript syntax, dependency audit). Latest browser smoke run: 44 tests, all passed.
- Preliminary current-tree scan found `.env.example` as the only secret/config filename match; `.gitignore` excludes `.env` and `.env.*` except `.env.example`. Basic repository searches for common credential prefixes returned no matches. This is not a final security clearance: historical `.env` exposure and provider-side key revocation cannot be independently verified from repository state.


## Library and Settings functional update (2026-11-12)
- Library now supports renaming projects and saved prompts with input validation; browser coverage confirms persistence. CI #482 and #483 passed all four jobs.
- Settings now applies the saved default mode to Vision Studio when Studio is selected as the default workspace; browser coverage confirms Advanced mode persists after reload. CI #484 and #485 passed all four jobs.
- Library and Settings implementation remain pending detailed manual acceptance; no production deployment was performed.


## Settings preference audit note (2026-11-12)
- Default workspace mode now applies to Vision Studio when Studio is selected as the default workspace; CI #484/#485 passed all four jobs. The browser suite verifies Advanced mode persists after reload.
- Prompt language is now active for Visual Lab generation: English/Hindi/Odia is sent from Settings, validated by the backend, and included in the AI output-language instruction. If AI composition fails for a non-English selection, the English deterministic fallback is disclosed with a review warning.


## Prompt language and output dialog verification (2026-11-12)
- Settings English/Hindi/Odia preference now flows through Visual Lab generation payload, backend validation, worker handoff, and AI output-language instruction. Non-English deterministic fallback is explicitly warned when AI composition fails. Unsupported languages are rejected before job creation.
- CI #506 (`43157161693`) passed all four jobs; the latest browser smoke suite ran 46 tests successfully, including output dialog accessibility, language payload, and settings persistence.
- Output sheet now has dialog/modal semantics, `aria-hidden` state sync, focus entry/return, Escape-to-minimize, and Tab focus loop.
- Remaining blockers: manual acceptance, real-provider prompt-quality review, real-image Vision Studio benchmark, controlled staging acceptance, final security review, and explicit production release approval. Production remains untouched.


## Prompt language and source-level accessibility audit (2026-11-12)
- CI #511 (`43157320003`, commit `6e2798e`) passed all four jobs: Python tests, Chromium desktop/mobile smoke tests, JavaScript syntax, and dependency audit.
- Prompt language preference flows through the Visual Lab browser payload, backend validation, worker, AI instruction, and output status. A non-English request with provider failure explicitly warns that the deterministic fallback remains English.
- Static accessibility scan covered all 14 HTML templates: no image missing alt text and no input/select/textarea lacking an ID or accessible-label hook. Dynamic JS-created buttons were reviewed and use visible text labels. This is not a replacement for screen-reader/manual acceptance.
- Manual acceptance, real-provider quality review, real-image benchmark, staging, final security review, and explicit production release approval remain outstanding. Production remains untouched.
