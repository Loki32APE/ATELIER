"""Reviewable prompt repair and variant generation for Vision Lab."""
from typing import Any, Dict, Optional

from .model_profiles import get_model_profile
from .vision_lab_provider import chat_completion
from .vision_lab_quality import quality_report_to_dict, validate_prompt_quality


def propose_prompt_repair(
    original_prompt: str,
    *,
    protected_instructions: str = "",
    model_id: Optional[str] = None,
    target_model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a repair proposal without replacing the original prompt."""
    profile = get_model_profile(target_model_id or "")
    original_quality = validate_prompt_quality(
        original_prompt,
        protected_instructions=protected_instructions,
        max_chars=profile.max_prompt_chars,
    )
    system = (
        "You are Atelier's prompt repair specialist. Improve clarity, coherence, "
        "and completeness while preserving all user intent. The protected "
        "instructions below must appear verbatim. Do not resolve creative conflicts "
        "by choosing for the user. Return only the repaired prompt."
    )
    user = (
        f"ORIGINAL PROMPT:\n{original_prompt}\n\n"
        f"PROTECTED USER INSTRUCTIONS (copy verbatim):\n{protected_instructions}\n\n"
        f"MODEL PROFILE: {profile.display_name}; advisory limit {profile.max_prompt_chars} characters. "
        "Repair only what can be improved without losing meaning."
    )
    response = chat_completion(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model_id=model_id,
        temperature=0.15,
        max_tokens=2200,
    )
    repaired = response["content"]
    repaired_quality = validate_prompt_quality(
        repaired,
        protected_instructions=protected_instructions,
        max_chars=profile.max_prompt_chars,
    )
    return {
        "status": "review_required" if repaired_quality.passed else "repair_failed_validation",
        "original_prompt": original_prompt,
        "repaired_prompt": repaired,
        "original_quality": quality_report_to_dict(original_quality),
        "repaired_quality": quality_report_to_dict(repaired_quality),
        "provider_model": response["model"],
        "user_decision_required": True,
    }
