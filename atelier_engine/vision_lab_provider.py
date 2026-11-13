"""OpenRouter-compatible provider adapter for Vision Lab AI reasoning.

Network access is opt-in at the call site. Secrets are read only from the
environment and are never returned in errors or response metadata.
"""
import os
from typing import Any, Dict, Optional

import requests


class ProviderError(RuntimeError):
    """Safe, user-displayable provider failure."""


def _model_id(model_id: Optional[str] = None) -> str:
    value = (model_id or os.getenv("VISION_LAB_MODEL") or os.getenv("MODEL") or "").strip()
    if not value:
        raise ProviderError("No Vision Lab model is configured.")
    return value


def chat_completion(
    messages,
    *,
    model_id: Optional[str] = None,
    temperature: float = 0.25,
    max_tokens: int = 1800,
    timeout: int = 45,
) -> Dict[str, Any]:
    """Call OpenRouter and return normalized content/model metadata."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ProviderError("AI provider is not configured. Add OPENROUTER_API_KEY in the server environment.")
    model = _model_id(model_id)
    if not isinstance(messages, list) or not messages:
        raise ProviderError("AI request messages are invalid.")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": max(0.0, min(float(temperature), 1.0)),
        "max_tokens": max(100, min(int(max_tokens), 4000)),
    }
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as exc:
        raise ProviderError("AI provider timed out. Please try again.") from exc
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (401, 403):
            message = "AI provider authentication failed. Check the server-side API configuration."
        elif status == 429:
            message = "AI provider rate limit reached. Please wait and retry."
        elif status and status >= 500:
            message = "AI provider is temporarily unavailable. Please retry."
        else:
            message = "Could not reach the AI provider. Please retry."
        raise ProviderError(message) from exc
    except (ValueError, TypeError) as exc:
        raise ProviderError("AI provider returned an unreadable response.") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("AI provider returned no prompt content.") from exc
    if not isinstance(content, str) or not content.strip():
        raise ProviderError("AI provider returned an empty prompt.")
    return {"content": content.strip(), "model": data.get("model") or model}
