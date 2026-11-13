"""Compatibility adapters for translating legacy Atelier requests.

These adapters are deliberately separate from Flask routes. They normalize
legacy form fields into the shared workspace contract without invoking models,
reading file bytes, or changing the existing /generate endpoint.
"""
from collections.abc import Mapping
from typing import Any, Dict, Optional

from .validation import validate_workspace_request

_LEGACY_TEXT_FIELDS = (
    ("subject_text", "Subject / physique"),
    ("hair_text", "Hairstyle"),
    ("pose_text", "Pose and action"),
    ("outfit_override", "Outfit override"),
)
_ALLOWED_DETAIL = frozenset({"fast", "balanced", "detailed"})
_ALLOWED_OUTPUT = frozenset({"full", "raw"})


def adapt_legacy_studio_request(
    form: Mapping[str, Any],
    uploaded_references: Mapping[str, Optional[Mapping[str, Any]]],
) -> Dict[str, Any]:
    """Translate the current /generate form contract into a Vision Studio payload.

    ``uploaded_references`` maps legacy multipart field names (``image1`` for
    Look and ``image2`` for Outfit) to metadata containing ``mime_type`` and
    optionally ``filename``. The caller must validate actual bytes separately
    with ``validate_reference_uploads`` before forwarding or persisting them.

    The function raises ValueError for malformed or unsupported legacy input.
    It does not change the existing route or its response/job semantics.
    """
    if not isinstance(form, Mapping):
        raise ValueError("Legacy form data must be a mapping.")
    if not isinstance(uploaded_references, Mapping):
        raise ValueError("Uploaded reference metadata must be a mapping.")

    output = str(form.get("output", "full")).strip().lower()
    if output not in _ALLOWED_OUTPUT:
        # Match the legacy /generate route, which defaults unknown values to full.
        output = "full"

    detail = str(form.get("detail", "balanced")).strip().lower()
    if detail not in _ALLOWED_DETAIL:
        detail = "balanced"

    reference_specs = (
        ("image1", "legacy-look", "look"),
        ("image2", "legacy-outfit", "outfit"),
    )
    references = []
    for field_name, reference_id, role in reference_specs:
        metadata = uploaded_references.get(field_name)
        if metadata is None:
            continue
        if not isinstance(metadata, Mapping):
            raise ValueError(f"Metadata for {field_name} must be an object.")
        references.append({
            "reference_id": reference_id,
            "role": role,
            "mime_type": metadata.get("mime_type"),
            "filename": metadata.get("filename"),
        })

    if output == "raw" and not any(ref["role"] == "look" for ref in references):
        raise ValueError("RAW output requires a Look reference (image1).")
    if output == "raw":
        references = [ref for ref in references if ref["role"] == "look"]
    elif not references:
        raise ValueError("At least one Look or Outfit reference is required.")

    instruction_lines = []
    for field_name, label in _LEGACY_TEXT_FIELDS:
        value = form.get(field_name, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be text.")
        # Match the existing /generate route's per-field input limit.
        value = value.strip()[:1500]
        if value:
            instruction_lines.append(f"{label}: {value}")

    payload = {
        "workspace": "vision_studio",
        "instructions": "\n".join(instruction_lines),
        "references": references,
        "options": {"detail": detail, "output": output},
    }
    validation = validate_workspace_request(payload)
    if not validation.valid:
        raise ValueError("; ".join(validation.errors))
    return payload
