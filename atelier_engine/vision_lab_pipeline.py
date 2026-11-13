"""Vision Lab intelligence orchestration with safe, reviewable AI composition."""
from collections.abc import Mapping
import re
from typing import Any, Dict, List, Optional, Tuple

from .model_profiles import get_model_profile
from .vision_lab_composer import compose_vision_lab_prompt
from .vision_lab_provider import chat_completion
from .vision_lab_quality import quality_report_to_dict, validate_prompt_quality
from .vision_lab_repair import propose_prompt_repair
from .vision_lab_structuring import structure_vision_lab_payload
from .vision_lab import VISION_LAB_MODULES


_SYSTEM_PROMPT = """You are Atelier Vision Lab, a senior creative director and visual prompt engineer.
Synthesize the structured creative brief into one coherent, production-ready image prompt.
Rules:
- Preserve every explicit user instruction verbatim as a protected instruction block.
- Treat user selections as intentional; never silently replace or omit them.
- Connect compatible choices into natural visual prose rather than mechanically concatenating fields.
- If choices conflict, explain the conflict and present alternatives; do not choose on the user's behalf.
- Do not invent identity or reference-image facts. Vision Lab is text-only and receives no images.
- Avoid repetition where it is truly redundant, but never remove a protected instruction.
- Return only the prompt text. Keep section headings only when they improve clarity."""


def _conflict_context(structured):
    warnings = [x for x in structured["rule_findings"] if x["severity"] == "warning"]
    if not warnings:
        return "No deterministic conflicts were detected."
    return "\n".join(
        f'{item["code"]}: {item["message"]} Values: {", ".join(item["values"])}'
        for item in warnings
    )


def _optimize_for_profile(prompt: str, profile):
    """Apply loss-aware model guidance; never silently truncate prompt content."""
    if len(prompt) <= profile.max_prompt_chars:
        return prompt, []
    return prompt, [
        f"Prompt exceeds {profile.display_name}'s advisory limit. Content was preserved; use the repair proposal to shorten it safely."
    ]



def _flatten_selected_details(value: Any, path: Tuple[str, ...] = ()):
    """Yield readable field paths and every non-empty selected scalar."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            next_path = path if str(key) == "choices" else path + (str(key),)
            yield from _flatten_selected_details(child, next_path)
    elif isinstance(value, list):
        for child in value:
            yield from _flatten_selected_details(child, path)
    elif isinstance(value, str) and value.strip():
        yield path, value.strip()
    elif isinstance(value, bool):
        yield path, "Yes" if value else "No"
    elif isinstance(value, (int, float)):
        yield path, str(value)


def _contains_exact_phrase(text: str, phrase: str) -> bool:
    """Match a selected phrase without accepting it inside a longer word."""
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.IGNORECASE))


def _restore_required_content(candidate: str, structured: Dict[str, Any]):
    """Append any omitted user instruction or selected value instead of losing it."""
    prompt = candidate if isinstance(candidate, str) else ""
    module_labels = dict(VISION_LAB_MODULES)
    existing = prompt.casefold()
    restored: List[str] = []
    selected_total = 0

    for module_id, selections in structured["module_selections"].items():
        for path, value in _flatten_selected_details(selections):
            selected_total += 1
            if _contains_exact_phrase(existing, value):
                continue
            field_label = " / ".join(part.replace("_", " ").replace("-", " ").capitalize() for part in path)
            label = module_labels.get(module_id, module_id)
            restored.append(f"{label} — {field_label}: {value}" if field_label else f"{label}: {value}")
            existing += "\n" + value.casefold()

    sections = []
    protected = structured["user_instructions"]
    instruction_restored = bool(protected and protected not in prompt)
    if instruction_restored:
        sections.append("Explicit user instructions (preserved verbatim):\n" + protected)
    if restored:
        sections.append(
            "Selected creative details retained from your brief:\n"
            + "\n".join("- " + item for item in restored)
        )
    if sections:
        prompt = (prompt.rstrip() + "\n\n" if prompt.strip() else "") + "\n\n".join(sections)

    return prompt, {
        "selected_details_total": selected_total,
        "selected_details_restored": len(restored),
        "instruction_restored": instruction_restored,
    }


def run_vision_lab_pipeline(
    payload: Any,
    *,
    model_id: Optional[str] = None,
    target_model_id: Optional[str] = None,
    use_ai: bool = True,
    repair: bool = False,
) -> Dict[str, Any]:
    """Run structure → reasoning → quality → optional repair → model profile.

    AI failure is surfaced clearly; deterministic draft is included as a
    recovery candidate, never represented as AI-generated output.
    """
    structured = structure_vision_lab_payload(payload)
    deterministic = compose_vision_lab_prompt(payload)
    profile = get_model_profile(target_model_id or "")
    protected = structured["user_instructions"]
    output_language = structured.get("language", "English")
    language_instruction = {
        "Hindi": "Write the complete final image prompt in Hindi. Keep proper names, model identifiers, and technical camera terms when they are clearer in their standard form.",
        "Odia": "Write the complete final image prompt in Odia. Keep proper names, model identifiers, and technical camera terms when they are clearer in their standard form.",
    }.get(output_language, "Write the complete final image prompt in English.")
    ai_status = "not_requested"
    candidate = deterministic["prompt"]
    provider_model = None
    provider_error = None

    if use_ai:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT + "\n\nOUTPUT LANGUAGE: " + language_instruction},
            {"role": "user", "content": (
                f'MODE: {structured["mode"]}\n'
                f'MODULE SELECTIONS: {structured["module_selections"]}\n'
                f'EXPLICIT USER INSTRUCTIONS (must be preserved verbatim):\n{protected}\n\n'
                f'RULE ENGINE FINDINGS:\n{_conflict_context(structured)}\n\n'
                f'DETERMINISTIC DRAFT FOR CONTEXT:\n{deterministic["prompt"]}'
            )},
        ]
        try:
            response = chat_completion(messages, model_id=model_id)
            candidate = response["content"]
            provider_model = response["model"]
            ai_status = "completed"
        except Exception as exc:
            provider_error = str(exc)
            ai_status = "failed"

    candidate, preservation = _restore_required_content(candidate, structured)
    candidate, optimization_warnings = _optimize_for_profile(candidate, profile)
    if ai_status == "failed" and output_language != "English":
        optimization_warnings.append(
            f"AI generation was unavailable; the deterministic fallback remains in English and does not honor the requested {output_language} output language."
        )
    if preservation["selected_details_restored"] or preservation["instruction_restored"]:
        optimization_warnings.append(
            "Some selected details or protected instructions were missing from the AI draft and have been restored verbatim. Review the retained-details section."
        )
    quality = validate_prompt_quality(
        candidate,
        protected_instructions=protected,
        max_chars=profile.max_prompt_chars,
    )

    repair_candidate = None
    if repair and not quality.passed:
        if not use_ai:
            repair_candidate = {
                "status": "not_generated",
                "reason": "AI repair was requested but AI composition is disabled.",
            }
        else:
            try:
                repair_candidate = propose_prompt_repair(
                    candidate, protected_instructions=protected, model_id=model_id,
                    target_model_id=target_model_id
                )
            except Exception as exc:
                repair_candidate = {
                    "status": "failed",
                    "reason": str(exc),
                    "user_decision_required": True,
                }

    return {
        "workspace": "vision_lab",
        "mode": structured["mode"],
        "output_language": output_language,
        "prompt": candidate,
        "deterministic_prompt": deterministic["prompt"],
        "ai_status": ai_status,
        "provider_model": provider_model,
        "provider_error": provider_error,
        "model_profile": {
            "model_id": profile.model_id,
            "display_name": profile.display_name,
            "max_prompt_chars": profile.max_prompt_chars,
            "preferred_format": profile.preferred_format,
            "supports_negative_prompt": profile.supports_negative_prompt,
        },
        "processing_status": (
            "needs_review" if structured["processing_status"] == "needs_review"
            or not quality.passed or ai_status == "failed"
            or preservation["selected_details_restored"] > 0
            or preservation["instruction_restored"] else "ready"
        ),
        "quality": quality_report_to_dict(quality),
        "selection_coverage": preservation,
        "optimization_warnings": optimization_warnings,
        "repair_candidate": repair_candidate,
        "rule_findings": structured["rule_findings"],
        "duplicate_instructions": structured["duplicate_instructions"],
        "instruction_integrity": "preserved" if quality.passed else "review_required",
    }
