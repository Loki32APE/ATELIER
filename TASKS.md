# Atelier Prompt Engine — Task Tracker

Follow this loop for every task:
`READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCS`

## Verified completed foundations
- [x] Shared schemas, workspace validation, and strict text-only Visual Lab backend boundary.
- [x] Magic-byte upload validation and bounded upload handling for Vision Studio.
- [x] Visual Lab seven-module backend registry, normalizer, deterministic rules, structuring, composer, model profiles, quality scoring, and non-destructive repair.
- [x] Vision Studio Look/Outfit separation, independent failure handling, analysis coverage, conflict priority, RAW contract, and quality review.
- [x] API rate limiting, input sanitization, and sanitized errors.
- [x] Optional Redis queue/worker reliability foundation and multiprocess recovery tests. Production queue remains disabled.
- [x] Dependency lockfiles, CI checks, dependency audit, and security/worker operations documentation.
- [x] GitHub Actions run `43049213077` passed all four jobs: Python tests, Chromium desktop/mobile smoke tests, JavaScript syntax, and dependency audit.

## Phase A — Frontend architecture and Visual Lab completion
- [x] **TASK-015 — Unified Catalog Service:** Shared service enforces an exact `/static/Catalog/` JSON allowlist, validates manifest IDs and catalog shapes, deduplicates requests, protects cache invalidation, and is loaded before Visual Lab/Theme/Jewellery consumers. Theme and Jewellery are migrated; repository-wide active frontend scan found no direct catalog JSON fetch calls. Manifest integrity and service contract tests pass in CI #459.
- [~] **TASK-016 — Seven-module UI and prompt preservation:** Every Basic/Advanced field across all seven modules has browser payload coverage. AI output omissions are now restored verbatim for selected values and protected instructions, with a visible review warning. Backend, all-module pipeline, and browser-notice tests pass in CI #426. Real-provider prompt-quality and manual acceptance review remain.
- [x] **TASK-017 — Compatibility guidance:** Added non-blocking Outfit/Pose styling suggestions for saree and lehenga movement/drape, plus heels and movement. Suggestions never change user selections; backend and browser regression tests pass.

## Phase B — Workspace management and responsive UI
- [~] **TASK-018 — Library (implementation and CI #459 verified; final action-by-action acceptance pending):** My Projects, Prompt Library, Reference Library, Favorites, History, search, filters, bulk actions, user-controlled Save, Save as New Version, version comparison, project and prompt rename/delete, validated JSON export/import, and safe local-storage migrations.
- [~] **TASK-019 — Settings (implementation and CI verified; final action-by-action acceptance pending):** Profile & Account, Appearance, Workspace Preferences, Prompt Preferences, AI Configuration, Storage & Data, and About Atelier. Saved default mode applies to both Visual Lab and Vision Studio. English/Hindi/Odia prompt language now flows from Settings through the Visual Lab payload, backend validation, worker handoff, and AI composition instruction. If AI is unavailable for a non-English selection, the deterministic English fallback is explicitly disclosed. Never expose provider secrets in the browser.
- [~] **TASK-020 — Home and responsive layout:** Use one adaptive interface driven by viewport width; no separate Desktop/Mobile preview mode. A public landing page now opens first, with responsive product overview, prompt example, workflow guide, FAQs, theme control, and a launch action into the saved workspace preference. Desktop/tablet/mobile visual acceptance remains.

## Phase C — Accessibility and quality hardening
- [~] **TASK-021 — Accessibility and UI states:** Keyboard picker navigation/focus restoration, visible focus, accessible labels, live status announcements, output pressed states, Vision Studio reference icon names, keyboard-operable minimized output dock and minimize handle, and the expanded output sheet's dialog semantics, focus management, Escape close, and Tab focus loop are implemented with browser coverage. Static image alt-text audit found no missing alt attributes in the checked workspace partials; broader semantic/async-state review remains.
- [~] **TASK-022 — Regression coverage:** Catalog, Library, Settings (navigation, backup/import, history clear, reset cancel/confirm), responsive viewport adaptation, keyboard, prompt-payload, reference removal, analysis retry, and Studio optimize success/failure browser coverage. Recheck the responsive suite after removing the preview-mode control; full action-by-action manual acceptance remains.
- [ ] **TASK-023 — Real-image benchmark:** Run controlled Vision Studio benchmark for pose, garment construction, saree details, fabric physics, and lighting accuracy. Record model/provider, fixtures, failures, and results.

## Phase D — Controlled staging and release readiness
- [~] **Deployment packaging:** Added a Python 3.11 pin, current Render web-service commands, accurate environment template, ignored local review artifacts, and CI coverage for all branches. Current approved Darkroom palette and prism-mark contracts replace stale Brushed Titanium asset assertions. Python suite passes (343 tests; 58 environment-dependent skips), JavaScript syntax passes (15 files), and local `/` responds with HTTP 200. Browser automation and real-Redis integration were skipped because Playwright/Redis are not configured in this environment. Existing-service staging acceptance, verified proxy configuration, TLS Redis provisioning, and release approval remain outstanding.
- [ ] **TASK-024 — Staging acceptance:** Run full E2E flows on the dedicated staging service, including authenticated TLS Redis, worker supervision/recovery, monitoring, and rollback. Do not enable production queue as part of this task.
- [ ] **TASK-025 — Final security review:** Verify current tree, historical credential response, dependency audit, secrets configuration, upload boundaries, rate limits, and production isolation.
- [ ] **TASK-026 — Production release:** Only after all acceptance criteria pass and the user explicitly authorizes the release. No production merge/deploy is included in ordinary development work.

## Current implementation checkpoint (2026-11-11)
- Added `static/js/catalog-service.js` with a strict `/static/Catalog/` path boundary, request de-duplication/cache, and theme/Layer 4/camera loaders.
- Migrated `theme.js` and `jewellery.js` to the shared service and loaded it before those consumers.
- Removed duplicate settings builders/reset functions from legacy scripts; scanned active `static/js/*.js` declarations and found no remaining duplicate function declarations.
- Added `tests/test_catalog_service_contract.py` and expanded Playwright coverage for Visual Lab catalog controls, Home view switching, Library flows, Reference Library storage, and Settings persistence. A fresh CI run is still required before these tasks can be marked complete.
- Added a seven-module Visual Lab preset catalog with Basic and Advanced controls, profile round-trip support, and saved default model/mode preferences. Added AI-output selection coverage: omitted selected values and protected instructions are restored verbatim in a labeled section, with `needs_review` and a visible warning rather than silent loss.
- Added unified Library tabs for My Projects, Prompt Library, Reference Library (IndexedDB), Favorites, and History; includes search, project assignment, bulk actions, side-by-side comparison, and Save as New Version.
- Added Settings sections for Profile & Account, Appearance, Workspace Preferences, Prompt Preferences, AI Configuration, Storage & Data, and About Atelier. Provider secrets remain server-side.
- Added Home Desktop/Mobile view switcher with persistent preference and responsive preview layout overrides.

### Visual Lab audit progress (2026-11-11)
- Fixed Creative Profile loading when no profile is selected; Load now stops instead of implicitly loading the first saved profile.
- Added a Chromium regression test to protect unsaved Visual Lab edits from accidental profile loading.
- Added conservative, informational Outfit/Pose guidance for saree drape and movement, lehenga movement, and heels with movement. No user choice is modified.
- Added backend tests for guidance severity, unchanged selections, and non-matching combinations, plus a browser test confirming guidance appears in the Visual Lab review notice.
- GitHub Actions run #426 (`43070212918`) passed all four jobs on commit `d4c559a`: Python tests, Chromium desktop/mobile, JavaScript syntax, and dependency audit. It includes the all-module AI selection-restoration tests and the browser review-notice test.
- TASK-016 remains in progress: all catalog fields are browser-tested in Basic and Advanced modes, and pipeline tests verify AI omission recovery across all seven modules. Real-provider prompt-quality and manual acceptance review remain.

## Task completion rule
A task is complete only when implementation, relevant automated tests, browser verification (where applicable), code review, and documentation updates have passed. A green CI run alone does not prove full product or staging readiness.


### Phase A verification update (2026-11-11)
- CI #459 (`43075808123`) completed successfully: all four jobs passed, including Chromium desktop/mobile smoke tests.
- TASK-015 is complete after strict catalog path/ID/schema hardening, manifest-to-file integrity tests, consumer script-order checks, and an active frontend JavaScript scan confirming no direct catalog JSON fetch remains outside the shared service. Theme and Jewellery use the shared service; Visual Lab loads the service before its consumer.
- TASK-016 remains in progress. Exact phrase restoration regression is covered by automated tests, but real-provider prompt-quality/manual acceptance has not been performed. Do not substitute deterministic/mock tests for provider acceptance.
- TASK-018/019/020 implementations and current CI checks are verified; detailed manual acceptance remains open. TASK-021/022 remain open for the explicitly listed audit/regression gaps.


### Phase B/C verification update (2026-11-12)
- Settings browser coverage now verifies all seven section panels and the single active `aria-current="page"` state (CI #466/#467 passed).
- Settings reset has both cancel-path preservation coverage and confirmed-path coverage. The confirmed-path test seeds every currently known Atelier local-storage key plus an IndexedDB reference record, accepts the destructive confirmation, and verifies the keys and `AtelierLibraryDB` are removed. CI #468 (`43152871072`) passed all four jobs.
- Vision Studio Look/Outfit inspect and remove icon actions now have explicit accessible names. CI #469 (`43152882048`) passed all four jobs.
- Audited frontend storage usage: active keys `pe_looks`, `pe_history`, `pe_subjects`, `pe_hairs`, `pe_poses`, `ape_projects`, `ape_settings_v1`, and `atelier_vision_lab_profiles_v1` are included in Settings reset. The obsolete `ape_view_mode` key remains in reset cleanup for older installs; Reference Library uses `AtelierLibraryDB`, which the reset also deletes.
- TASK-019 remains in progress pending manual action-by-action acceptance. TASK-021/022 remain open for the wider semantic/async-state audit and remaining end-to-end acceptance. CI success is not a substitute for real-provider, real-image, or staging acceptance.


### Accessibility and regression update (2026-11-12)
- Added semantic button behaviour and Enter-key activation to the minimized prompt output dock; the browser test verifies keyboard focus, activation, dock dismissal, and output expansion.
- CI #472 (`43153631455`), #473 (`43153642958`), and #474 (`43153658239`) passed all four jobs. #474 includes the new minimized-dock keyboard regression test.
- The existing Studio browser suite already covers reference removal, analysis retry, optimize success, and optimize failure; these are now explicitly reflected in TASK-022 rather than listed as missing.
- TASK-021 and TASK-022 remain in progress because full semantic/async-state review and manual action-by-action acceptance are still outstanding.


### Output accessibility verification (2026-11-12)
- Converted the output sheet minimize handle from a clickable `div` into a labeled native button while preserving its compact visual treatment.
- Extended the output workflow browser test to verify that the minimized dock opens with Enter and that the labeled minimize handle returns the output to the dock.
- CI #475 (`43154033792`), #476 (`43154054564`), #477 (`43154162675`), #478 (`43154175756`), and #479 (`43154194220`) passed all four jobs. The latest browser run executed 44 tests successfully.
- Current-tree security reconnaissance found only `.env.example` among secret/config filename patterns; `.gitignore` excludes `.env` and `.env.*` while allowing `.env.example`. Basic repository code searches found no common key-prefix matches. This is preliminary reconnaissance only, not the final security review; historical `.env` exposure and provider-side revocation still require independent confirmation.


### Library and Settings functional regression update (2026-11-12)
- Added Rename project and Rename prompt actions to Library with empty/length validation and local persistence. Browser test verifies both renames survive in their respective local-storage records. CI #482 (`43154810622`) and #483 (`43154821206`) passed all four jobs.
- Fixed Settings default mode application for Vision Studio when it is the selected default workspace. Browser test verifies Advanced mode and the advanced controls persist after reload. CI #484 (`43155100115`) and #485 (`43155113563`) passed all four jobs.
- TASK-018 remains in progress pending manual acceptance; TASK-019 remains in progress pending full action-by-action acceptance and final preference semantics review.


### Settings preference gap (2026-11-12)
- Verified `defaultMode` now applies to Vision Studio as well as Visual Lab; CI #484 (`43155100115`) and #485 (`43155113563`) passed all four jobs. Latest browser run executed 46 tests successfully.
- Resolved: the Prompt language preference is now validated and passed to the Visual Lab provider instruction. Tests cover supported/unsupported values, worker handoff, and provider language instruction (CI #506).


### Prompt language and output dialog verification (2026-11-12)
- Wired the saved English/Hindi/Odia prompt language through Visual Lab browser payload, server-side draft validation, worker handoff, and AI system instruction. Unsupported language values are rejected before job creation. If AI fails for a non-English selection, the deterministic English fallback is surfaced with an explicit warning.
- Added tests for language validation, worker handoff, provider instruction, frontend payload contract, and fallback disclosure. CI #506 (`43157161693`) passed all four jobs.
- Expanded output sheet accessibility: dialog role and modal semantics, `aria-hidden` state sync, focus moved into the dialog on open and back to the dock on minimize, Escape-to-minimize, and Tab focus loop. Final browser verification is CI #506; latest suite ran 46 tests successfully.
- Intermediate CI runs exposed test-only issues (slide-in animation timing and RAW output title expectation); the final combined run passed. No production deployment or Render change was made.


### Prompt language and final static accessibility audit (2026-11-12)
- Prompt Preferences English/Hindi/Odia now flows from local Settings into the Visual Lab request, is validated server-side, reaches the worker, and is included in the AI output-language instruction. Output metadata announces the requested language. If AI composition fails for a non-English request, the English deterministic fallback is clearly disclosed with a review warning.
- Added coverage for supported/unsupported language values, worker handoff, provider instruction, frontend payload contract, output-language status, and fallback disclosure.
- CI #511 (`43157320003`, commit `6e2798e`) passed all four jobs: Python tests, Chromium desktop/mobile smoke tests, JavaScript syntax, and dependency audit.
- Static accessibility scan covered all 14 HTML templates: no image missing alt text and no input/select/textarea lacking an ID or accessible-label hook. Dynamic button creation in active JS was reviewed; generated controls use visible text labels. This is a source-level audit, not a substitute for screen-reader/manual acceptance.
- TASK-019 remains open for action-by-action manual acceptance. TASK-021/022 remain open for full manual/screen-reader and end-to-end acceptance. Real-provider, real-image, staging, security, and production-release gates remain open.

### Library filtered-selection and Reference Library storage verification (2026-11-12)
- Fixed Prompt Library and History bulk selection so select-all applies only to currently visible filtered/search results; changing the search or project filter clears stale selections.
- Fixed Reference Library upload-limit accounting so invalid files do not consume the 100-image allowance; valid images are counted after validation.
- Added graceful error reporting for bulk reference deletion failures and ensured IndexedDB handles close when transaction setup fails.
- Added Chromium regression coverage for filtered bulk selection, valid-image upload counting at the 100-image boundary, and IndexedDB bulk-delete failure handling.
- GitHub Actions CI #518 (`43158896021`) passed all four jobs: Python unit tests, Chromium desktop/mobile browser smoke tests, JavaScript syntax validation, and dependency security audit.
- TASK-018 remains in progress pending full manual action-by-action acceptance. TASK-021/022 remain open for broader accessibility and end-to-end acceptance. Real-provider, real-image, staging, final security, and production-release gates remain open. No production merge or Render deployment was performed.


### Reference Library deletion and selection verification (2026-11-12)
- Fixed individual Reference Library image deletion so IndexedDB transaction failures are caught and surfaced as a visible status message instead of an unhandled rejected promise.
- Fixed Reference Library select-all so it clears any stale selection before selecting the current reference set.
- Added a Chromium regression test that forces a readwrite IndexedDB transaction failure during individual deletion and verifies the visible error state without a page error.
- GitHub Actions CI #521 (`43159584900`, commit `a03c677f395fc89295d7fa25c4aba8644bf96b5b`) passed all four jobs: Python unit tests, Chromium desktop/mobile browser smoke tests, JavaScript syntax validation, and dependency security audit.
- TASK-018 remains in progress pending full manual action-by-action acceptance. TASK-021/022 remain open for broader accessibility and end-to-end acceptance. Real-provider, real-image, staging, final security, and production-release gates remain open. No production merge or Render deployment was performed.


### Reference Library selection-state synchronization (2026-11-12)
- Fixed the Reference Library master select-all checkbox so it reflects the current selected count after individual selection changes and after an image is deleted; partial selection is represented with the indeterminate state.
- Stale selected IDs are pruned against the current IndexedDB records when the list renders.
- Added a Chromium regression test covering select-all, individual deselection/reselection, and deletion while maintaining the master checkbox state.
- GitHub Actions CI #523 (`43160145470`, commit `461bbb4bd719cdcbd63b7e04b833bc6018b52a52`) passed all four jobs: Python unit tests, Chromium desktop/mobile browser smoke tests, JavaScript syntax validation, and dependency security audit.
- TASK-018 remains in progress pending full manual action-by-action acceptance. TASK-021/022 remain open for broader accessibility and end-to-end acceptance. Real-provider, real-image, staging, final security, and production-release gates remain open. No production merge or Render deployment was performed.


### Library master-selection synchronization and CI verification (2026-11-12)
- Fixed Prompt Library and History master select-all checkboxes so checked/indeterminate state tracks individual selections and only the currently visible filtered/search result set.
- Stale Prompt Library and History selected IDs are pruned against currently visible items during rendering; individual selection changes immediately synchronize the master checkbox.
- Added Chromium regression coverage for Prompt Library and History master-checkbox state after individual selection changes.
- Stabilized Reference Library browser fixtures: upload-limit coverage now uploads valid tiny PNG files through the browser rather than seeding malformed IndexedDB blobs; selection-state coverage waits for asynchronous IndexedDB-backed UI updates before asserting.
- GitHub Actions CI #529 (`43161309536`, commit `2cf6aa24dfdc43286c8e0af87ccbf50102964e56`) passed all four jobs: Python unit tests, Chromium desktop/mobile browser smoke tests, JavaScript syntax validation, and dependency security audit.
- TASK-018 remains in progress pending full manual action-by-action acceptance. TASK-021/022 remain open for broader accessibility and end-to-end acceptance. Real-provider, real-image, staging, final security, and production-release gates remain open. No production merge or Render deployment was performed.


### Library keyboard and favorite-flow verification (2026-11-12)
- Library tabs support Home and End keyboard navigation alongside left/right arrows.
- Browser coverage verifies Home/End selection and restores the Prompt Library tab before favoriting an item.
- GitHub Actions CI #533 (`43162564554`, commit `95da21f6f537b9245680bc4e44d4095edd691b88`) passed all four jobs: Python tests, Chromium desktop/mobile smoke tests, JavaScript syntax validation, and dependency audit.
- The code and browser-test changes are present in this workspace. CI verifies the commit; action-by-action manual acceptance and the real-provider, real-image, staging, historical-credential, and release gates remain open.
