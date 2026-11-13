# Atelier Prompt Engine — UI Mockup Brief

Give this file to a UI design or mockup AI as product context for a **full UI/UX makeover**. The current product description explains what exists today; it does not limit the redesign. The AI may reorganize, simplify, add, replace, or recommend removing features when that makes the product clearer and more useful.

## Redesign assignment

Redesign Atelier Prompt Engine from the user's point of view, rather than just repainting the current screens. Review the workflows and decide what should be:

- **Kept** because it supports the product's core purpose.
- **Improved or combined** because it is confusing, repetitive, hard to find, or too space-consuming.
- **Removed** when it adds clutter without enough user value. Explain any meaningful loss or trade-off.
- **Added** when it solves a real need for prompt creation, review, reuse, or accessibility. Do not add features just to make the screens look busier.

The core purpose to preserve is helping users create, refine, and organize high-quality image prompts through either text-led construction or reference-led analysis. All other current UI and feature choices are open to redesign. Clearly label proposed functions as **new proposals**, not features that already exist.

Deliver a coherent desktop and mobile concept, including the main navigation, key screen layouts, primary user flows, and important empty/loading/success/error states. Include a short keep / improve / remove / add recommendation list with reasons. Prefer a small set of clear, complete workflows over a long feature checklist.

## Product at a glance

Atelier Prompt Engine is a creative workspace for **building detailed image prompts**. It helps a user describe a visual idea, combine it with reference images when useful, and refine the resulting prompt before using it in an external image-generation tool.

The product is a prompt-engineering workspace. Do not present it as an image generator: its main output is an editable text prompt, not a rendered image.

## Main navigation

- **Home** — overview and entry point to the two creation workspaces; layout adapts automatically to the available screen.
- **Studio / Vision Studio** — reference-led prompt creation using Look and Outfit images.
- **Visual Lab** — text-only, structured prompt-building workspace.
- **Library** — projects, prompts, reference images, favorites, and generation history.
- **Settings** — local profile, appearance, workspace and prompt defaults, storage, and product information.
- **About, Help & Feedback, Terms of Use, Privacy** — supporting information pages.

On phones, use a fixed bottom navigation for the primary workspaces. On wider screens, use a clear side navigation that can open and close without obscuring the Atelier brand mark.

## Core workflows and features

### Vision Studio

1. Add a **Look reference** for scene, pose, framing, and visual identity.
2. Add an **Outfit reference** for garment, construction, styling, and fabric detail.
3. Add optional creative direction and choose Basic or Advanced mode.
4. Choose analysis detail: Fast, Balanced, or Detailed.
5. Generate a master prompt or a RAW prompt.
6. Review separate Look and Outfit analysis, coverage, conflicts, and notes. Retry analysis for the selected references when needed.
7. Edit, copy, or save the resulting prompt.

Advanced controls include outfit text override; saved physique, hairstyle, and pose profiles; and additional creative instructions. Reference upload areas support inspect/zoom and remove actions.

### Visual Lab

Visual Lab builds a creative brief from seven structured sections:

1. Appearance & Identity
2. Outfit & Styling
3. Poses & Expressions
4. Themes & Environment
5. Lighting & Composition
6. Camera & Photography
7. Output & Rendering

Users can work in Basic or Advanced mode, write their own descriptions, choose from catalog controls, add constraints, use a sample brief, and save/load/delete creative profiles. The product can flag conflicting choices without silently changing them. The final master prompt is editable and can be copied, re-validated, or reviewed with repair suggestions. Explicit instructions should remain visible and protected.

Visual Lab is text-first. Image references belong in Vision Studio.

### Library

- Create and organize projects.
- Search and filter saved prompts; favorite, rename, delete, and save new versions.
- Compare prompt versions side by side.
- Export and import a prompt backup.
- Keep reusable reference images in a separate Reference Library on the current device.
- Search and manage generation history independently from saved prompts.

### Settings

- Local profile and appearance preferences.
- Default workspace, Basic/Advanced mode, and preferred desktop/mobile view.
- Default target image model, analysis detail, and prompt language.
- Storage usage, backup import/export, history clearing, and local-data reset.
- AI provider configuration is server-side. Never put API keys or provider secrets in mockup UI, browser settings, or user-facing copy.

## Approved visual reference

Use `atelier_prompt_engine_brand_identity_production_assets_pack.html` as the final visual source of truth. Preserve its Darkroom Obsidian and Warm Archival Paper modes, Editorial Vermilion accent, wireframe prism mark, Instrument Sans / Plus Jakarta Sans / JetBrains Mono fonts, and icon language without redesigning those assets. Apply the reference to the actual Atelier workflows while retaining their working behavior.

The user approved this pack on 2026-11-13. Do not present new competing visual directions or change the pack's brand choices.

When a direction is approved, prioritize legibility, control, focused creative work, compact selectable lists, clear states, and comfortable mobile touch targets. Use simple, consistent line icons and keep labels visible for important actions.

## Responsive behavior

- Design both a full desktop workspace and a phone-sized layout.
- Desktop should use available width for useful work areas and keep key controls near their related content.
- Mobile should be touch-first, vertically ordered, and safe around the fixed bottom navigation.
- Keep the menu control separate from the Atelier logo/wordmark.
- Use one adaptive UI across desktop, tablet and mobile; do not provide desktop/mobile preview-mode controls.
- Avoid horizontal overflow, clipped headings, hidden form labels, and overlays covering controls.

## Mockup guardrails

- Preserve the two distinct creation modes: reference-led Studio and text-only Visual Lab.
- Do not invent image rendering, account syncing, cloud storage, collaboration, or live model selection beyond the listed product behavior.
- Do not remove Library, Settings, policies, or editing/review steps from the information architecture.
- Avoid generic AI visuals: harsh gradients, pure-white canvases, rainbow or neon palettes, purple/black styling, glowing radial orbs, liquid glass, heavy shadows, dot-grid wallpaper, and default pastel bento-card layouts.
- Avoid oversized pill controls, three feature cards in a row, colored card-edge stripes, animated arrows, hover motion everywhere, emoji icons, sparkle motifs, and fake testimonials.
- Keep interface text useful and specific. Do not use placeholder testimonials or claim that the product generates images.

## Suggested mockup set

Create a connected set of screens showing:

1. Home dashboard that reflows naturally from desktop through tablet to phone widths.
2. Vision Studio with empty reference viewfinder, uploaded-reference review, and generated prompt states.
3. Visual Lab in Basic and Advanced modes, including compact selectable options and the seven-section brief.
4. Library with Prompt Library, Reference Library, and version comparison states.
5. Settings with workspace/prompt preferences and local data controls.

Use realistic fashion, portrait, textile, and editorial photography only as example reference imagery. Keep the UI itself faithful to the matte graphite, warm ivory, and restrained brass Atelier identity.
