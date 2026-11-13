"""Probe a short list of current OpenRouter free chat endpoints.

Reads OPENROUTER_API_KEY only from the process environment. Never prints the
key or raw provider response. Failed attempts stop early on account/network
errors so they do not waste the free-request allowance.
"""
import os
import re
import sys

import requests


ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MODELS_ENDPOINT = "https://openrouter.ai/api/v1/models"
KEY_ENDPOINT = "https://openrouter.ai/api/v1/key"
MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/free",
]


def main():
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        print("Probe skipped: OPENROUTER_API_KEY is not set.")
        print("SELECTED_MODEL=")
        return 0

    print("Checking current free text models with a tiny test prompt.")
    # A no-key GET separates basic Python/network connectivity from chat API
    # failures without consuming a model request.
    try:
        catalog = requests.get(MODELS_ENDPOINT, timeout=16)
        catalog_type = catalog.headers.get("Content-Type", "unknown")
        print(f"Connection check: HTTP {catalog.status_code} [{catalog_type}]")
        if not catalog.ok or "json" not in catalog_type.lower():
            print("Python cannot read OpenRouter's public JSON endpoint; skipping model requests.")
            print("SELECTED_MODEL=")
            return 0
    except requests.RequestException as exc:
        print(f"Connection check: could not reach OpenRouter ({type(exc).__name__}); skipping model requests.")
        print("SELECTED_MODEL=")
        return 0

    working = []
    attempted = 0
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # Validate the key without generating a model completion or using free quota.
    try:
        key_check = requests.get(KEY_ENDPOINT, headers=headers, timeout=16)
        key_type = key_check.headers.get("Content-Type", "unknown")
        if key_check.ok and "json" in key_type.lower():
            print("Key check: accepted (no model request used).")
        else:
            ray = key_check.headers.get("CF-Ray", "")
            ray_note = f", cf_ray={ray[:80]}" if ray else ""
            print(f"Key check: HTTP {key_check.status_code} [{key_type}]{ray_note}, body_bytes={len(key_check.content)} (no model request used).")
            if key_check.status_code in (401, 403):
                print("OpenRouter rejected this key; create or check the key in your OpenRouter account.")
                print("SELECTED_MODEL=")
                return 0
            if not key_check.ok or "json" not in key_type.lower():
                print("Key endpoint gave an unusual response; checking one chat request directly.")
    except requests.RequestException as exc:
        print(f"Key check: could not complete ({type(exc).__name__}); skipping model requests.")
        print("SELECTED_MODEL=")
        return 0

    for model in MODELS:
        try:
            attempted += 1
            response = requests.post(
                ENDPOINT,
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Reply with OK."}],
                    "max_tokens": 32,
                },
                timeout=16,
            )
        except requests.Timeout:
            print(f"NO  {model} — timed out; stopping further probes.")
            break
        except requests.RequestException:
            print(f"NO  {model} — could not connect; stopping further probes.")
            break

        if response.ok:
            try:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError):
                content = ""
            if isinstance(content, str) and content.strip():
                actual = data.get("model") or model
                working.append((model, actual))
                print(f"YES {model} — response from {actual}")
                continue
            print(f"NO  {model} — provider returned no text; HTTP {response.status_code}.")
            continue

        code = response.status_code
        content_type = response.headers.get("Content-Type", "unknown")
        try:
            body = response.json()
            error = body.get("error", {}) if isinstance(body, dict) else {}
            detail = error.get("message", "") if isinstance(error, dict) else str(error)
            detail = re.sub(r"\s+", " ", str(detail)).strip()
        except (ValueError, TypeError):
            detail = ""
        if not detail:
            detail = re.sub(r"\s+", " ", response.text).strip()
        if key:
            detail = detail.replace(key, "[redacted]")
        detail = re.sub(r"sk-or-v1-[A-Za-z0-9]+", "[redacted]", detail)[:180]
        if code in (401, 402, 403, 429):
            labels = {
                401: "key authentication rejected",
                402: "account/provider access rejected",
                403: "access forbidden",
                429: "free request limit reached",
            }
            print(f"NO  {model} — HTTP {code}: {labels[code]}; stopping further probes.")
            break
        suffix = f" ({detail})" if detail else ""
        server = response.headers.get("Server", "")[:80]
        via = response.headers.get("Via", "")[:80]
        request_id = response.headers.get("X-Request-ID") or response.headers.get("X-OpenRouter-Request-Id") or ""
        cf_ray = response.headers.get("CF-Ray", "")
        diagnostic = ", ".join(part for part in (f"server={server}" if server else "", f"via={via}" if via else "", f"request_id={request_id[:80]}" if request_id else "", f"cf_ray={cf_ray[:80]}" if cf_ray else "", f"body_bytes={len(response.content)}") if part)
        print(f"NO  {model} — HTTP {code} [{content_type}]{suffix}; {diagnostic}; trying the next free model.")
        if code == 400 and "json" not in content_type.lower():
            print("Response was not JSON; stopping because the request may be blocked by a proxy or network gateway.")
            break

    selected = working[0][0] if working else ""
    print(f"Working models: {len(working)} of {attempted} tested ({len(MODELS)} available in this check).")
    print(f"SELECTED_MODEL={selected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
