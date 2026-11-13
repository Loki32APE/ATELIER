# Vision Lab catalog data

This directory contains the JSON catalogs used by the legacy Scratchpad settings UI in `static/js/theme.js`.

## Files

- `global.json` — shared prompt limits, prompt ordering, shot types, visibility rules, and art styles.
- `index.json` — catalog version and the list of available themes.
- `Themes/<theme-id>.json` — theme-specific title, vibe, background, lighting, environment, and recommended tags.
- `outfit/`, `makeup/`, `jewellery/`, `accessories/`, and other category folders — structured selection data consumed by the relevant UI modules.

## Adding a theme

1. Add a JSON file under `Themes/`.
2. Give it a unique `id` that matches its filename.
3. Add the theme to the `themes` array in `index.json`.
4. Keep the theme's fields consistent with the existing theme files.

Do not use the retired `validate.py` instructions from older catalog revisions; that script expected a different schema and was removed. Catalog validation will be maintained against the current v2 structure as part of QA.
