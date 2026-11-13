"""Model capability registry and conservative prompt adaptation policies.

Profiles describe formatting constraints, not guaranteed model quality. Unknown
models receive a neutral profile and are never silently treated as compatible.
"""
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    display_name: str
    max_prompt_chars: int
    preferred_format: str
    supports_negative_prompt: bool
    notes: str = ""


_PROFILES: Dict[str, ModelProfile] = {
    "openai/gpt-image": ModelProfile(
        "openai/gpt-image", "OpenAI GPT Image", 12000, "natural_language", False,
        "Use clear, direct visual instructions; avoid assuming a separate negative-prompt field.",
    ),
    "google/gemini-2.5-flash-image": ModelProfile(
        "google/gemini-2.5-flash-image", "Google Gemini Image", 12000, "natural_language", False,
        "Use coherent scene descriptions and explicit preservation constraints.",
    ),
    "black-forest-labs/flux.1-pro": ModelProfile(
        "black-forest-labs/flux.1-pro", "FLUX.1 Pro", 8000, "concise_natural_language", False,
        "Prefer concise, concrete visual details and avoid redundant phrasing.",
    ),
    "midjourney": ModelProfile(
        "midjourney", "Midjourney", 6000, "compact_visual", True,
        "Keep the prompt visually specific; platform parameters are handled separately.",
    ),
    "unknown": ModelProfile(
        "unknown", "Unspecified model", 12000, "natural_language", False,
        "Neutral formatting only; no unsupported model-specific assumptions.",
    ),
}


def get_model_profile(model_id: str = "") -> ModelProfile:
    """Resolve known model IDs and safe family aliases."""
    key = (model_id or "").strip().lower()
    if key in _PROFILES:
        return _PROFILES[key]
    for known in _PROFILES:
        if known != "unknown" and key.startswith(known + ":"):
            return _PROFILES[known]
    return _PROFILES["unknown"]


def list_model_profiles():
    """Return serializable public profile summaries."""
    return [
        {
            "model_id": item.model_id,
            "display_name": item.display_name,
            "max_prompt_chars": item.max_prompt_chars,
            "preferred_format": item.preferred_format,
            "supports_negative_prompt": item.supports_negative_prompt,
            "notes": item.notes,
        }
        for key, item in sorted(_PROFILES.items()) if key != "unknown"
    ]
