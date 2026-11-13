# Product Requirements Document (PRD)

## Product Name
**Atelier Prompt Engine**
*Tagline: "Where Imagination Meets Intelligence."*

## Problem Statement
Creators, digital artists, and AI photography enthusiasts struggle to translate complex visual ideas or multiple reference images into technically accurate, model-optimized AI image generation prompts. Generic prompt generators simply concatenate keywords without understanding visual coherence, fabric physics, lighting dynamics, anatomical framing, or model-specific nuances.

## Target Users
- **Beginners:** Users who want high-quality, professional AI photography and fashion prompts using simple guided presets without deep technical knowledge.
- **Professional Creators & Prompt Engineers:** Advanced users who require granular control over facial anatomy, garment construction (e.g., saree draping, zari work, fabric tension), multi-source lighting, camera optics, and reference-based prompt synthesis.

## Goal
Build a world-class Creative Intelligence Ecosystem that empowers users to construct prompts from scratch (**Visual Lab**) or extract and synthesize visual intelligence from reference photographs (**Vision Studio**), optimized for leading image generation models (Google Nano Banana, OpenAI GPT Image, Midjourney, FLUX, Ideogram).

## Product Ecosystem (Workspaces)
1. **Atelier Home:** Main dashboard with quick access and workspace switching, adapting automatically to the available screen.
2. **Visual Lab (Text-Only Creative Construction):** Build prompts from scratch across 7 structured creative modules. Strictly prohibits image references.
3. **Vision Studio (Reference Intelligence & Prompt Engineering):** Upload independent Look and Outfit reference images, apply creative directives/overrides, and synthesize Master or RAW prompts.
4. **Library & Settings:** Unified workspace for saved prompts, version history, reusable creative profiles (Physique, Hairstyle, Pose), and AI model configuration.
5. **Vision Engine (Future Roadmap - Out of Current Scope):** Unified orchestration combining Visual Lab modules and Vision Studio reference intelligence.

## Core Features & MVP Scope

### A. Operating Modes (Across Workspaces)
- **Basic Mode:** Clean, beginner-friendly interface with essential controls and curated presets. Produces high-quality, detailed prompts automatically.
- **Advanced Mode:** Professional multi-panel workspace unlocking granular parameters, custom overrides, saved profile libraries, and deep prompt validation controls.

### B. Visual Lab (7 Core Modules)
1. **Appearance & Identity:** Gender presentation, age, skin tone/texture, facial structure, eye/lip details, hairline, body proportions, identity preservation instructions.
2. **Outfit & Styling:** Garment categories (e.g., Sambalpuri Saree, Western, Editorial), neckline, sleeves, fabric composition/physics, embroidery, drapery, jewellery, footwear, makeup coordination.
3. **Poses & Expressions:** Body orientation, angles, hand/arm placement, head tilt, gaze direction, facial expressions, weight distribution, pose-outfit compatibility.
4. **Themes & Environment:** Indoor/outdoor locations, architectural style, interior decor, weather, time of day, atmospheric depth, cultural styling.
5. **Lighting & Composition:** Key/fill/rim/back lighting, light temperature, shadow softness, rule of thirds, framing (close-up to full-body), depth of field.
6. **Camera & Photography:** Camera/lens models, focal length, aperture (f-stop), shutter speed, ISO, bokeh characteristics, colour science, film emulation.
7. **Output & Rendering Intelligence:** Aspect ratio, orientation, resolution, realism level, negative prompts, target AI model selection.

### C. Vision Studio (Reference Intelligence)
- **Dual-Lens Reference Input:** Independent **Look Reference** (framing, pose, gaze, lighting, environment, visible range; excludes facial identity) and **Outfit Reference** (garment construction, fabric weave, embroidery, folds, jewellery, footwear).
- **Processing Modes:** Fast, Balanced, and Detailed analysis modes.
- **Creative Directives & Overrides:** Explicit user overrides for Subject Physique, Hairstyle, Pose & Action, and Outfit Text Override, plus Reusable Creative Profiles.
- **Dual Prompt Outputs:**
  - **Master Prompt:** Combines Look analysis, Outfit analysis, and user directives into a comprehensive, conflict-resolved prompt.
  - **RAW Prompt:** Uses Look reference analysis + custom directives + a dedicated Fabric Physics block + direct outfit reference instruction (`OUTFIT: take the outfit from reference image.`).
- **Analysis UX:** Independent reference analysis status (Ready, Partial, Failed), coverage score, visual conflict review panel, and retry functionality.

### D. Hybrid Prompt Intelligence Engine
- **6-Stage Pipeline:** Input Collection -> Data Structuring -> Deterministic Rule Engine -> Mood-Aware AI Composer -> Model-Specific Optimizer -> Quality Validator.
- **Quality Validator & Auto-Repair:** Evaluates completeness (25%), consistency (25%), instruction preservation (20%), model compatibility (20%), and clarity (10%). Proposes an automatic repair while preserving the original prompt for side-by-side comparison (Accept, Edit, or Reject).
- **Prompt Controls & Versioning:** Copy, Edit, Regenerate, Improve Details, Expand, Simplify, Re-validate Edits, and User-Controlled Saving ("Save" and "Save as New Version").

## Out of Scope (Current Version)
- **Vision Engine:** Combined Lab + Studio workspace (reserved for future phase).
- **Image references inside Visual Lab:** Visual Lab must remain 100% text-only.
- **Automatic saving of every generated prompt:** Only user-approved prompts are saved to persistent storage; temporary generations stay in session/history.
- **Direct image rendering/hosting:** Atelier engineers precision prompts; it does not host heavy GPU image-diffusion pipelines directly.

## Success Criteria
1. Users can configure all 7 modules in Visual Lab (Basic & Advanced) and generate model-optimized prompts without any image reference fields present.
2. Users can upload Look and/or Outfit photos in Vision Studio, review analysis coverage and conflict warnings, and generate accurate Master or RAW prompts.
3. Explicit user instructions (e.g., Outfit Override, Custom Pose) always take priority over reference analysis or AI inference without silent overwriting.
4. Quality Validator scores prompts accurately and offers non-destructive repair proposals.
5. Application runs reliably within Render Free Tier and OpenRouter free-model token/rate limits.
