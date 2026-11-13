"""Provider-neutral Vision Lab structure and normalization rules.

This module defines the seven creative-construction modules and converts
validated user selections into a stable draft for later rule and AI stages.
Vision Lab is deliberately text-only; image references belong to Vision Studio.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Any, Dict, Tuple


VISION_LAB_MODULES: Tuple[Tuple[str, str], ...] = (
    ("appearance_identity", "Appearance & Identity"),
    ("outfit_styling", "Outfit & Styling"),
    ("poses_expressions", "Poses & Expressions"),
    ("themes_environment", "Themes & Environment"),
    ("lighting_composition", "Lighting & Composition"),
    ("camera_photography", "Camera & Photography"),
    ("output_rendering", "Output & Rendering Intelligence"),
)
VISION_LAB_MODES = frozenset({"basic", "advanced"})
VISION_LAB_LANGUAGES = frozenset({"English", "Hindi", "Odia"})
MAX_SELECTION_MODULES = len(VISION_LAB_MODULES)
MAX_SELECTION_DEPTH = 5
MAX_SELECTION_TEXT = 20_000


@dataclass(frozen=True)
class VisionLabDraft:
    """Normalized, immutable-at-the-boundary Vision Lab user draft."""

    mode: str
    instructions: str
    selections: Mapping[str, Any]
    language: str = "English"


def _validate_json_value(value: Any, path: str, depth: int = 0) -> None:
    """Reject non-JSON values and bound nested user-controlled data."""
    if depth > MAX_SELECTION_DEPTH:
        raise ValueError(f"{path} is nested too deeply.")
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain a finite number.")
        return
    if isinstance(value, str):
        if len(value) > MAX_SELECTION_TEXT:
            raise ValueError(f"{path} exceeds {MAX_SELECTION_TEXT} characters.")
        return
    if isinstance(value, list):
        if len(value) > 200:
            raise ValueError(f"{path} contains too many items.")
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]", depth + 1)
        return
    if isinstance(value, Mapping):
        if len(value) > 200:
            raise ValueError(f"{path} contains too many fields.")
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip() or len(key) > 100:
                raise ValueError(f"{path} has an invalid field name.")
            _validate_json_value(item, f"{path}.{key}", depth + 1)
        return
    raise ValueError(f"{path} contains an unsupported value type.")


def normalize_vision_lab_draft(payload: Any) -> VisionLabDraft:
    """Validate and normalize structured Vision Lab selections without AI calls."""
    if not isinstance(payload, Mapping):
        raise ValueError("Vision Lab input must be an object.")

    if "references" in payload and payload["references"]:
        raise ValueError(
            "Vision Lab is text-only; image references must be handled by Vision Studio."
        )
    if any(key in payload for key in ("image", "images", "image_reference")):
        raise ValueError(
            "Vision Lab does not accept image fields; use Vision Studio for references."
        )

    mode = payload.get("mode", "basic")
    if not isinstance(mode, str) or mode.lower() not in VISION_LAB_MODES:
        raise ValueError("Vision Lab mode must be 'basic' or 'advanced'.")
    mode = mode.lower()

    instructions = payload.get("instructions", "")
    if not isinstance(instructions, str):
        raise ValueError("Vision Lab instructions must be text.")
    if len(instructions) > MAX_SELECTION_TEXT:
        raise ValueError(f"Vision Lab instructions must be {MAX_SELECTION_TEXT} characters or fewer.")

    language = payload.get("language", "English")
    if not isinstance(language, str) or language not in VISION_LAB_LANGUAGES:
        raise ValueError("Vision Lab language must be English, Hindi, or Odia.")

    selections = payload.get("selections", {})
    if not isinstance(selections, Mapping):
        raise ValueError("Vision Lab selections must be an object.")
    known = {key for key, _ in VISION_LAB_MODULES}
    unknown = set(selections) - known
    if unknown:
        raise ValueError("Unknown Vision Lab module(s): " + ", ".join(sorted(map(str, unknown))))
    if len(selections) > MAX_SELECTION_MODULES:
        raise ValueError("Too many Vision Lab modules were supplied.")

    clean: Dict[str, Any] = {}
    for module_id, value in selections.items():
        if not isinstance(value, (Mapping, list, str)):
            raise ValueError(f"Selection for {module_id} must be an object, list, or text.")
        _validate_json_value(value, f"selections.{module_id}")
        clean[module_id] = value

    return VisionLabDraft(
        mode=mode,
        instructions=instructions.strip(),
        selections=clean,
        language=language,
    )
