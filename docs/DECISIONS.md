# Architecture Decision Records

## ADR-001: Separate Workspaces — Visual Lab, Vision Studio, Future Vision Engine
- Decision: Maintain two active independent workspaces: Visual Lab for text-based seven-module prompt construction and Vision Studio for reference-image analysis and synthesis. Reserve Vision Engine for future combined workflows.
- Reason: Prevents UI clutter while allowing shared platform services.

## ADR-002: Visual Lab Is Strictly Text-Only
- Decision: Reject image uploads and image-reference metadata in Visual Lab at both UI and backend validation boundaries. Internal legacy identifiers such as `vision_lab` and `/synthesize-scratch` may remain for compatibility.
- Reason: Image-reference intelligence belongs exclusively in Vision Studio.

## ADR-003: Hybrid Prompt Intelligence Engine
- Decision: Combine deterministic data structuring and rule validation with mood-aware AI composition and model-specific optimizers.
- Reason: Templates alone are rigid; unguided LLM generation can hallucinate or drop explicit constraints. The hybrid pipeline balances structure and natural language.

## ADR-004: Decouple Target Image Model from AI Reasoning Provider
- Decision: The reasoning/composition LLM provider is independent from the target image generation model.
- Reason: Provider changes must not break target-model formatting.

## ADR-005: Non-Destructive Quality Validation and Repair
- Decision: Score completeness (25%), consistency (25%), instruction preservation (20%), model compatibility (20%), and clarity (10%). Return repairs as separate candidates alongside the original.
- Reason: Users retain control; no AI operation silently overwrites the original prompt.

## ADR-006: User-Controlled Saving
- Decision: Temporary generations stay in bounded session history (target maximum 15). Only explicit Save or Save as New Version actions write to permanent Library storage.
- Reason: Prevents unwanted persistence and silent overwrites.

## ADR-007: Vision Studio Conflict Priority
- Decision: Apply this order: (1) explicit user directives/overrides, (2) domain-primary reference (Look for pose/framing/lighting/environment; Outfit for garment/fabric/jewellery), (3) AI inference.
- Reason: Prevents visual bleed between references and overrides.

## ADR-008: Brushed Titanium and Responsive Layout
- Status: Superseded by ADR-012 for brand styling. Responsive desktop/tablet/mobile layout remains in effect; the separate preview switcher was later removed in favor of automatic viewport adaptation.

## ADR-009: Safe Branching and Staging
- Decision: Develop on `visual-lab-rebuild`; keep production repository/service untouched until full QA and explicit approval.
- Reason: Protects the live app from rebuild regressions.

## ADR-010: User-Facing Name Is Visual Lab; Internal Identifiers Stay Compatible
- Decision: Display **Visual Lab** in the product UI and user-facing documentation. Retain existing `vision_lab` Python/JS/API identifiers unless a separately tested migration is required.
- Reason: Honors the approved product naming while avoiding unnecessary API, storage, and test breakage.

## ADR-011: Never Silently Drop Visual Lab Selections
- Decision: After AI composition, compare the candidate prompt against every normalized selected scalar and the protected instruction text. If any detail is absent, append the missing content verbatim in clearly labeled sections, expose a preservation warning, and set processing status to `needs_review`. Never truncate content to meet a target model limit.
- Reason: A fluent AI rewrite must not silently erase a user's explicit creative choices. Deterministic recovery keeps the final prompt reviewable while preserving the original AI composition.

## ADR-012: Production Brand Assets Pack
- Decision: Use the user's production assets pack as the exact source of truth for brand mark, dual-mode palette, fonts, icon set, and component styling. Preserve the established app behavior and adapt the visual assets to its templates.
- Dark mode: Darkroom Obsidian. Light mode: Warm Archival Paper. Editorial Vermilion is the accent in both.
- Status: Approved by user on 2026-11-13.
- Reason: The application must work as a premium creative workspace on desktop and mobile.

## ADR-013: One Adaptive Viewport Layout
- Decision: The interface adapts to the actual available screen width. Do not offer separate desktop/mobile preview modes or persist a preferred viewport mode.
- Status: Approved by user on 2026-11-13.
- Reason: The same app should fit whatever screen the user opens it on.
