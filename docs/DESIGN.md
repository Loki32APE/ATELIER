# Design System & UI/UX Specification

## 1. Brand Direction
- Brand: Atelier Prompt Engine — "Where Imagination Meets Intelligence."
- Active identity: **Darkroom Obsidian & Warm Archival Paper**, following the approved production assets pack.
- Aesthetic: restrained creative workspace, solid charcoal or warm paper surfaces, vermilion accent, custom wireframe prism mark, clear typography.
- Avoid generic blue/white SaaS styling, excessive neon, cluttered forms, cramped desktop layouts, and unnecessary human/robot illustrations.

## 2. Approved Dual-Mode Palette
Use the exact token values in `static/css/brand-tokens.css` and `static/brand-tokens.json`.

| Mode | Canvas | Surface | Elevated | Accent |
|---|---|---|---|---|
| Darkroom Obsidian | `#111215` | `#181A1F` | `#20232A` | Editorial Vermilion `#E04F33` |
| Warm Archival Paper | `#F6F4EF` | `#FFFFFF` | `#ECE9E1` | Editorial Vermilion `#E04F33` |

Gold should remain a restrained accent (approximately 3–5% of the viewport), not a dominant fill. Existing approved brand tokens are the source of truth; do not create parallel token names without migration.

## 3. Typography
- Display headings: Instrument Sans.
- UI and body: Plus Jakarta Sans.
- Prompt output and technical metadata: JetBrains Mono.
- Keep the attached brand pack's logo and typography unchanged.

## 4. Responsive Layout
- One adaptive interface reflows to the device viewport; do not add separate desktop/mobile preview modes.
- Desktop (>=1024px): full-width multi-panel layout; persistent left navigation; central workspace; right prompt-intelligence/output panel. Do not retain a 540px desktop width cap.
- Tablet (768–1023px): adaptive two-column layout and collapsible navigation/panels.
- Mobile (<768px): touch-first vertical flow, compact expandable modules, sticky bottom navigation, and a bottom-sheet prompt output.
- Minimum interactive touch target: 44px.

## 5. Workspace UX
- Visual Lab: equal hierarchy for all seven modules; Basic/Advanced mode toggle; mode changes must preserve current selections.
- Vision Studio: clear Discover -> Direct -> Compose progression; Look and Outfit reference scopes remain separate.
- Library: My Projects, Prompt Library, Reference Library, Favorites, History; search, filters, and bulk actions.
- Settings: Profile & Account, Appearance, Workspace Preferences, Prompt Preferences, AI Configuration, Storage & Data, About Atelier.

## 6. Accessibility & Interaction
- Use semantic buttons for upload zones, accordions, tabs, and actions.
- All interactive elements must be keyboard reachable and usable with Enter/Space.
- Provide visible focus indicators, accessible names, aria-expanded state where applicable, and meaningful alt text.
- Do not rely on color alone to communicate status.

## 7. Required UI States
Every async feature must have:
- Loading: skeleton or stage-aware progress.
- Empty: clear guidance and next action.
- Partial/Conflict: non-blocking warning with explanation and recovery/retry where applicable.
- Error: safe, human-readable message and recovery action.
- Success: clear completion feedback and next step.

## 8. Prompt Output Controls
Generated prompts support Copy and Edit. Keep the original output available when editing or repairing. Revalidation must be explicit. Saving is user-controlled; never silently overwrite a saved prompt or version.
