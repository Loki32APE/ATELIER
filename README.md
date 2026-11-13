# Atelier Prompt Engine

Atelier is a responsive creative workspace for building image prompts. **Vision Studio** analyses separate Look and Outfit references; **Visual Lab** builds structured text briefs with Basic and Advanced controls. The public landing page introduces both workspaces. User projects, prompt history, preferences, and reference-library data are stored in the browser unless an explicitly configured server feature is used.

## Stack and project map

- Python 3.11, Flask, Gunicorn; vanilla JavaScript and CSS.
- `app.py` serves the web app; `worker.py` is an optional queue worker.
- `atelier_engine/` contains validation, prompt composition, provider adapters, uploads, and job handling.
- `templates/` contains page markup; `static/js/`, `static/css/`, `static/Catalog/`, and `static/brand/` contain frontend modules, styles, catalogs, and approved brand assets.
- `tests/` contains Python and browser-contract coverage. `docs/` describes architecture and operational constraints.

## Local development

Use Python 3.11 and Node.js 22. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --require-hashes -r requirements.lock
python -m flask --app app run --debug
```

Open `http://127.0.0.1:5000`. The Flask app does not load `.env` files automatically. To test AI-backed features on Windows, run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\run_local_with_key.ps1"`; it asks for the OpenRouter key without saving it and starts the app on port `5001`. Without a key, the app still loads but provider-backed requests will not work. Redis and the worker queue are not needed for normal local use.

## Deploy an existing Render web service

Set the service to **Python 3**, then use:

- Build command: `python -m pip install --require-hashes -r requirements.lock`
- Start command: `gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT app:app`
- Health check path: `/`
- Pin Python with the checked-in `.python-version` file.

Configure these values in Render's Environment settings; never commit their values:

- `APP_ENV=production`
- `APP_URL=https://<your-public-service-host>`
- `OPENROUTER_API_KEY` with a valid provider key
- `RATELIMIT_STORAGE_URI` with an authenticated TLS Redis URL (`rediss://...`)
- `TRUSTED_PROXY_HOPS` only after verifying the exact trusted proxy chain; leave it unset or `0` otherwise.

Production startup intentionally fails unless the rate-limit store is authenticated TLS Redis. Do not point it at an unauthenticated or plaintext Redis service. Keep `JOB_QUEUE_ENABLED=false`; enabling the queue requires a separately reviewed staging setup, TLS Redis configuration, and a supervised worker. See [deployment security](docs/DEPLOYMENT_SECURITY.md) before changing these settings.

This working copy has no Git metadata or remote configured. These instructions prepare an existing service configuration; they do not publish code or change a live deployment.

## Quality checks

Run the checks when making a code change:

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p "test_browser_smoke.py" -v
Get-ChildItem static/js/*.js | ForEach-Object { node --check $_.FullName }
```

The browser suite needs Playwright and Chromium. GitHub Actions runs the Python suite, browser smoke tests, JavaScript syntax check, and dependency audit on pushes and pull requests.

## Security and release notes

Keep API keys, `.env` files, user uploads, and secret-bearing logs out of Git. Do not enable production queue mode or deploy to production based only on passing CI; complete the controlled staging and release review tracked in `TASKS.md` and `docs/DEPLOYMENT_SECURITY.md` first.
