# Comprehensive Test Plan

## 1. Automated Checks
Run the relevant checks for every change:
- Python: `python -m unittest discover -s tests -v`
- JavaScript syntax: `node --check` for every active file in `static/js/`
- Browser: Playwright Chromium desktop/mobile smoke tests.
- Security: dependency audit against the committed lockfiles.
- CI: verify every required GitHub Actions job completed successfully.

## 2. Backend and Workspace Boundaries
- Visual Lab accepts valid text selections across all seven modules in Basic and Advanced modes.
- Visual Lab rejects image files and reference roles (`look`, `outfit`, `identity`, `inspiration`).
- Oversized keywords, malformed JSON, unknown module keys, and invalid target model IDs are rejected safely.
- Vision Studio Master accepts supported Look and/or Outfit references according to its contract.
- Vision Studio RAW requires Look reference and excludes Outfit reference from garment-description synthesis.
- Explicit user overrides outrank reference analysis and AI inference.

## 3. Upload Security
- Accept valid JPEG, PNG, and WebP magic-byte signatures.
- Reject spoofed MIME types/extensions.
- Reject oversized single files, aggregate payloads, and excess reference counts before expensive processing.
- Verify stream pointers are reset after validation.
- Verify filenames are sanitized.

## 4. Visual Lab Intelligence
- Deterministic rules detect framing, pose, environment, lighting, and duplicate-instruction conflicts.
- Explicit user selections survive normalization and composition.
- Quality scoring uses the approved five dimensions and weights.
- Repair returns a separate candidate and preserves original output.
- Target image model ID is passed accurately to model-specific optimization.
- Copy and Edit work; edits can be revalidated.

## 5. Vision Studio Intelligence
- Look and Outfit analyses fail independently; successful results survive partial failures.
- Coverage checks detect missing required sections.
- Conflict priority follows explicit override > domain-primary reference > AI inference.
- RAW contract includes the exact Outfit reference instruction and required Fabric Physics block.
- Retry after failure and progress cleanup after success/failure work correctly.

## 6. Library and Settings
- Save is user-controlled; temporary generations are not silently persisted.
- Save as New Version creates a distinct version.
- Compare, rename, delete, export, import, and migration preserve data integrity.
- Settings persist only supported preferences and never expose secrets.

## 7. Responsive and Accessibility Matrix
- Mobile: 375px; verify touch targets >=44px, no horizontal overflow, and usable output sheet.
- Tablet: 768px; verify adaptive two-column layout and collapsible panels.
- Desktop: 1440px; verify full-width multi-panel layout with no legacy 540px cap.
- Verify the same workspace adapts at desktop, tablet, and phone viewport widths without a mode switch.
- Verify Tab focus, Enter/Space activation, Escape modal close, accessible names, alt text, and visible focus.

## 8. Staging Acceptance
- Execute complete Visual Lab and Vision Studio user flows on the dedicated staging service.
- Run real-image benchmark for pose, garment/saree detail, fabric physics, and lighting.
- Exercise queue submission, polling, worker termination/restart recovery, Redis authentication/TLS, monitoring, and rollback in a controlled environment.
- CI smoke tests are necessary but do not replace real staging acceptance.
- Production release remains blocked until the full checklist passes and the user explicitly approves.
