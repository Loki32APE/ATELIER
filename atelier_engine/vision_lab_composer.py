"""Deterministic, provider-neutral prompt composition for Vision Lab.

This foundation turns the canonical seven-module handoff into a readable
prompt draft. It does not call an AI provider, resolve conflicts, or rewrite
user choices. Vision Lab remains text-only.
"""
from collections.abc import Mapping
from typing import Any, Dict, List, Tuple

from .vision_lab import VISION_LAB_MODULES
from .vision_lab_structuring import structure_vision_lab_payload


def _label(value: str) -> str:
    """Convert a machine-style field name into a readable label."""
    return value.replace("_", " ").replace("-", " ").strip().capitalize()


def _render_value(value: Any, indent: int = 0) -> List[str]:
    """Render every supplied scalar in a stable, human-readable order."""
    prefix = " " * indent
    if isinstance(value, str):
        return [prefix + value] if value.strip() else []
    if isinstance(value, bool):
        return [prefix + ("Yes" if value else "No")]
    if isinstance(value, (int, float)):
        return [prefix + str(value)]
    if isinstance(value, Mapping):
        lines: List[str] = []
        for key in sorted(value, key=lambda item: str(item).casefold()):
            child = value[key]
            label = _label(str(key))
            if isinstance(child, (Mapping, list)):
                lines.append(prefix + label + ":")
                lines.extend(_render_value(child, indent + 2))
            else:
                rendered = _render_value(child)
                if rendered:
                    lines.append(prefix + label + ": " + rendered[0].strip())
        return lines
    if isinstance(value, list):
        lines: List[str] = []
        for child in value:
            rendered = _render_value(child, indent)
            lines.extend(prefix + "- " + item.strip() for item in rendered)
        return lines
    return []


def compose_vision_lab_prompt(payload: Any) -> Dict[str, Any]:
    """Compose a stable prompt draft while preserving every explicit choice.

    The input uses the same shape accepted by structure_vision_lab_payload.
    Warnings are surfaced as review notes; they are never auto-resolved.
    """
    structured = structure_vision_lab_payload(payload)
    module_labels = dict(VISION_LAB_MODULES)
    sections: List[str] = [
        "Create a cohesive visual result using the following creative direction."
    ]
    included_modules: List[str] = []

    for module_id, _ in VISION_LAB_MODULES:
        if module_id not in structured["module_selections"]:
            continue
        rendered = _render_value(structured["module_selections"][module_id])
        if not rendered:
            continue
        included_modules.append(module_id)
        sections.append(module_labels[module_id] + ":\n" + "\n".join(rendered))

    instructions = structured["user_instructions"]
    if instructions:
        sections.append(
            "Explicit user instructions (preserve exactly):\n" + instructions
        )

    warnings = [
        finding["message"]
        for finding in structured["rule_findings"]
        if finding["severity"] == "warning"
    ]
    if warnings:
        sections.append(
            "Review required before finalization:\n"
            + "\n".join("- " + message for message in warnings)
        )

    duplicate_notes = structured["duplicate_instructions"]
    if duplicate_notes:
        sections.append(
            "Repeated details detected (retained; review for optional cleanup):\n"
            + "\n".join("- " + item for item in duplicate_notes)
        )

    return {
        "workspace": "vision_lab",
        "mode": structured["mode"],
        "prompt": "\n\n".join(sections),
        "processing_status": structured["processing_status"],
        "included_modules": included_modules,
        "rule_findings": structured["rule_findings"],
        "duplicate_instructions": duplicate_notes,
        "instruction_integrity": "preserved",
        "composition_engine": "deterministic_foundation",
    }
