"""Canonical, provider-neutral payload assembly for Vision Lab.

The structuring layer combines validated selections and deterministic rule
findings into one stable handoff contract for future AI Composer adapters.
Vision Lab remains text-only; references are owned by Vision Studio.
"""
from copy import deepcopy
from typing import Any, Dict

from .vision_lab import VISION_LAB_MODULES
from .vision_lab_rules import evaluate_vision_lab_rules


SCHEMA_VERSION = "1.0"


def structure_vision_lab_payload(payload: Any) -> Dict[str, Any]:
    """Return a canonical JSON-compatible payload without rewriting user input.

    Raises:
        ValueError: If the supplied draft violates the Vision Lab boundary.
    """
    report = evaluate_vision_lab_rules(payload)
    draft = report.draft

    # Use the approved module registry order, not arbitrary request key order.
    module_selections = {
        module_id: deepcopy(draft.selections[module_id])
        for module_id, _ in VISION_LAB_MODULES
        if module_id in draft.selections
    }

    findings = [
        {
            "code": item.code,
            "severity": item.severity,
            "message": item.message,
            "modules": list(item.modules),
            "values": list(item.values),
        }
        for item in sorted(
            report.findings,
            key=lambda finding: (finding.code, finding.severity, finding.modules, finding.values),
        )
    ]

    has_warnings = any(item["severity"] == "warning" for item in findings)
    return {
        "workspace": "vision_lab",
        "schema_version": SCHEMA_VERSION,
        "mode": draft.mode,
        "language": draft.language,
        "user_instructions": draft.instructions,
        "module_selections": module_selections,
        "rule_findings": findings,
        "duplicate_instructions": list(report.duplicate_instructions),
        "instruction_integrity": "preserved",
        "processing_status": "needs_review" if has_warnings else "ready",
    }
