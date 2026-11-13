# Repository Guidelines

## Project Structure & Module Organization

- `app.py` and `worker.py` contain the Flask web process and optional worker entry point.
- `atelier_engine/` holds prompt composition, validation, model adapters, uploads, and job infrastructure.
- `templates/` contains page templates and reusable workspace partials. `static/js/`, `static/css/`, `static/Catalog/`, and `static/brand/` contain frontend code, styles, structured catalogs, and approved brand assets.
- `tests/` contains Python and browser-contract tests. `docs/`, `TASKS.md`, and `.cursor/rules/` describe architecture, task status, and project-specific practices.

## Build, Test, and Development Commands

Run commands from the repository root with the project virtual environment active:

```powershell
python -m flask --app app run --debug
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p "test_browser_smoke.py" -v
Get-ChildItem static/js/*.js | ForEach-Object { node --check $_.FullName }
```

The first command starts the local Flask app. The second runs the Python suite; the third runs Chromium smoke tests and requires Playwright plus Chromium. The last checks JavaScript syntax. There is no separate frontend build step. Redis queue mode is opt-in; do not enable it for routine local development.

## Coding Style & Naming Conventions

Use four spaces for Python indentation and follow existing type, validation, and error-handling patterns. Use descriptive `snake_case` for Python functions and variables, `PascalCase` for classes, and `test_*.py` for test files and methods. Keep browser modules and styles in their existing directories; use lowercase kebab-case for new frontend filenames. Use native HTML controls and accessible labels, and keep provider credentials server-side.

## Testing Guidelines

Add or update focused regression tests for changed behavior. Python tests use `unittest`; browser coverage uses Playwright/Chromium. Run the relevant tests and JavaScript syntax check before proposing a change. Do not treat mocked provider tests as proof of real-provider quality. Record remaining acceptance work in `TASKS.md`.

## Commits and Pull Requests

No Git history is included in this checkout to establish an existing commit format. Use short imperative messages with a scope, such as `Fix: preserve Visual Lab selections`. Pull requests should explain the user-visible change, list verification commands and results, link related tasks, and include desktop/mobile screenshots for visual changes. Call out deployment or configuration changes explicitly.

## Security and Configuration

Never commit API keys, tokens, `.env` files, user uploads, or logs containing secrets. Use `.env.example` only for blank or clearly fake placeholders. Keep production deployment and Redis enablement separate from normal development; follow `docs/DEPLOYMENT_SECURITY.md` and obtain explicit release approval.
