"""Deterministic rule checks for structured, text-only Vision Lab drafts.

This layer reports actionable conflicts without rewriting user selections.
It is provider-neutral and deliberately does not make AI or network calls.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any, Dict, List, Tuple

from .vision_lab import VisionLabDraft, normalize_vision_lab_draft


@dataclass(frozen=True)
class RuleFinding:
    """One explainable rule-engine observation."""

    code: str
    severity: str
    message: str
    modules: Tuple[str, ...] = ()
    values: Tuple[str, ...] = ()


@dataclass(frozen=True)
class VisionLabRuleReport:
    """Rule report plus unchanged, normalized input for the next pipeline stage."""

    draft: VisionLabDraft
    findings: Tuple[RuleFinding, ...]
    duplicate_instructions: Tuple[str, ...]
    protected_instructions: str

    @property
    def has_conflicts(self) -> bool:
        return any(item.severity == "warning" for item in self.findings)


# Only compare concepts when the user has supplied a recognizable value.
# Synonyms are intentionally small and conservative to avoid false positives.
_CONCEPTS = {
    "framing": {
        "full body": "full_body", "full-body": "full_body", "full length": "full_body",
        "close up": "close_up", "close-up": "close_up", "extreme close up": "close_up",
        "wide shot": "wide", "establishing shot": "wide", "medium shot": "medium",
    },
    "pose": {
        "standing": "standing", "stand": "standing", "sitting": "sitting",
        "seated": "sitting", "lying": "lying", "laying": "lying", "kneeling": "kneeling",
    },
    "environment": {
        "indoor": "indoor", "inside": "indoor", "outdoor": "outdoor", "outside": "outdoor",
    },
    "lighting": {
        "daylight": "daylight", "bright daylight": "daylight", "night lighting": "night",
        "night": "night", "dark night": "night",
    },
    "subject_count": {
        "single person": "single", "one person": "single", "solo": "single",
        "two people": "group", "group": "group", "crowd": "group", "multiple people": "group",
    },
}

_KEY_ALIASES = {
    "framing": "framing", "shot": "framing", "shot_type": "framing", "camera_framing": "framing",
    "pose": "pose", "action": "pose", "body_position": "pose",
    "environment": "environment", "setting": "environment", "location_type": "environment",
    "lighting": "lighting", "light": "lighting", "lighting_style": "lighting",
    "subject_count": "subject_count", "number_of_people": "subject_count",
}
_TEXT_KEYS = {"value", "selected", "label", "name", "choice", "description"}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _scalar_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, Mapping):
        for key in _TEXT_KEYS:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def _walk(value: Any, module_id: str, path: str = ""):
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            category = _KEY_ALIASES.get(key_text)
            text = _scalar_text(child)
            if category and text:
                yield category, text, module_id
            yield from _walk(child, module_id, f"{path}.{key}")
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child, module_id, path)


def _concept(category: str, value: str) -> str:
    normalized = _norm(value)
    for phrase, concept in _CONCEPTS[category].items():
        if _norm(phrase) == normalized:
            return concept
    return ""


def _find_duplicates(draft: VisionLabDraft) -> Tuple[str, ...]:
    seen: Dict[str, str] = {}
    duplicates: List[str] = []
    candidates = [draft.instructions]
    for module_value in draft.selections.values():
        def collect(value):
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
            elif isinstance(value, Mapping):
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
        collect(module_value)

    for item in candidates:
        key = _norm(item)
        if len(key) < 3:
            continue
        if key in seen and item not in duplicates:
            duplicates.append(item)
        else:
            seen[key] = item
    return tuple(duplicates)



def _selected_text(draft: VisionLabDraft, module_id: str, field_id: str) -> str:
    """Read a selected catalog value without changing the normalized draft."""
    module = draft.selections.get(module_id, {})
    if not isinstance(module, Mapping):
        return ""
    choices = module.get("choices", module)
    if not isinstance(choices, Mapping):
        return ""
    return _scalar_text(choices.get(field_id))


def _outfit_pose_guidance(draft: VisionLabDraft) -> Tuple[RuleFinding, ...]:
    """Return conservative, non-blocking styling suggestions for movement."""
    garment = _norm(_selected_text(draft, "outfit_styling", "garment_type"))
    pose = _norm(_selected_text(draft, "poses_expressions", "pose"))
    footwear = _norm(_selected_text(draft, "outfit_styling", "footwear"))
    findings: List[RuleFinding] = []

    moving = pose in {"walking", "dynamic movement"}
    seated = pose in {"sitting", "seated", "kneeling"}

    if "saree" in garment and moving:
        findings.append(RuleFinding(
            code="OUTFIT_POSE_GUIDANCE",
            severity="info",
            message="Styling suggestion: for a moving saree pose, consider specifying pleat stability, pallu direction, and natural fabric movement.",
            modules=("outfit_styling", "poses_expressions"),
            values=(garment, pose),
        ))
    elif "saree" in garment and seated:
        findings.append(RuleFinding(
            code="OUTFIT_POSE_GUIDANCE",
            severity="info",
            message="Styling suggestion: for a seated or kneeling saree pose, consider specifying pleat placement and pallu position to preserve a natural drape.",
            modules=("outfit_styling", "poses_expressions"),
            values=(garment, pose),
        ))

    if "lehenga" in garment and moving:
        findings.append(RuleFinding(
            code="OUTFIT_POSE_GUIDANCE",
            severity="info",
            message="Styling suggestion: for a moving lehenga pose, consider specifying skirt flare, hem clearance, and natural fabric movement.",
            modules=("outfit_styling", "poses_expressions"),
            values=(garment, pose),
        ))

    if footwear in {"heels", "high heels"} and moving:
        findings.append(RuleFinding(
            code="OUTFIT_POSE_GUIDANCE",
            severity="info",
            message="Styling suggestion: with heels and a moving pose, consider describing stable foot placement and natural balance.",
            modules=("outfit_styling", "poses_expressions"),
            values=(footwear, pose),
        ))

    return tuple(findings)


def evaluate_vision_lab_rules(payload: Any) -> VisionLabRuleReport:
    """Normalize a draft and report clear contradictions without changing it."""
    draft = normalize_vision_lab_draft(payload)
    findings: List[RuleFinding] = []
    grouped: Dict[str, Dict[str, List[Tuple[str, str]]]] = {}

    for module_id, selection in draft.selections.items():
        for category, text, source_module in _walk(selection, module_id):
            concept = _concept(category, text)
            if concept:
                grouped.setdefault(category, {}).setdefault(concept, []).append((source_module, text))

    labels = {
        "framing": "Framing", "pose": "Pose", "environment": "Environment",
        "lighting": "Lighting", "subject_count": "Subject count",
    }
    for category, concepts in grouped.items():
        if len(concepts) > 1:
            modules = tuple(sorted({m for entries in concepts.values() for m, _ in entries}))
            values = tuple(sorted({v for entries in concepts.values() for _, v in entries}))
            findings.append(RuleFinding(
                code=f"{category.upper()}_CONFLICT",
                severity="warning",
                message=f"{labels[category]} selections appear contradictory. Review the choices before composing the prompt.",
                modules=modules,
                values=values,
            ))

    findings.extend(_outfit_pose_guidance(draft))

    duplicates = _find_duplicates(draft)
    if duplicates:
        findings.append(RuleFinding(
            code="DUPLICATE_INSTRUCTION",
            severity="info",
            message="Repeated instruction text was detected. It will be reported, not silently removed.",
            values=duplicates,
        ))

    return VisionLabRuleReport(
        draft=draft,
        findings=tuple(findings),
        duplicate_instructions=duplicates,
        protected_instructions=draft.instructions,
    )
