"""Vision Studio reference intelligence, guardrails and prompt contracts."""
from collections.abc import Mapping
from typing import Any, Dict, List

_REFERENCE_RULES = {
    "look": {
        "analyze": [
            "framing and visible body range", "pose, action and gaze",
            "lighting and camera", "background and environment", "makeup",
            "garments visible in the look reference", "jewellery and accessories",
            "footwear when visible",
        ],
        "ignore": ["facial identity details", "hairstyle and hair length"],
    },
    "outfit": {
        "analyze": [
            "garment construction and type", "fabric, weave, texture and colour",
            "neckline, sleeves and garment length", "embroidery, zari, sequins and prints",
            "drape, pleats, folds, tension and fabric physics",
            "jewellery, accessories and footwear visible in the outfit reference",
        ],
        "ignore": [
            "wearer identity and facial features", "hairstyle", "skin tone",
            "background", "pose and gaze", "lighting and camera",
        ],
    },
}
_DIRECTIVE_FIELDS = (
    ("subject_text", "subject_physique", "subject physique"),
    ("hair_text", "hairstyle", "hairstyle"),
    ("pose_text", "pose_action", "pose and action"),
    ("outfit_override", "outfit", "outfit reference details"),
    ("additional_instructions", "additional_instructions", "applicable prompt sections"),
)
MAX_DIRECTIVE_CHARS = 1500

_ANALYSIS_TASK_LABELS = {
    'look': ('FRAMING', 'VISIBLE RANGE', 'POSE AND ACTION', 'AND GAZE', 'FOOTWEAR', 'LIGHTING AND CAMERA', 'BACKGROUND AND ENVIRONMENT', 'MAKEUP', 'GARMENTS', 'JEWELLERY AND ACCESSORIES', 'AVOID'),
    'look_pose': ('FRAMING', 'VISIBLE RANGE', 'POSE AND ACTION', 'AND GAZE', 'FOOTWEAR', 'AVOID'),
    'look_detail': ('LIGHTING AND CAMERA', 'BACKGROUND AND ENVIRONMENT', 'MAKEUP', 'GARMENTS', 'JEWELLERY AND ACCESSORIES', 'AVOID'),
    'outfit': ('GARMENTS', 'FABRIC PHYSICS', 'FOOTWEAR', 'JEWELLERY AND ACCESSORIES', 'LIPSTICK', 'MEHNDI', 'AVOID'),
}

def validate_reference_analysis(task: str, description: str) -> Dict[str, Any]:
    """Measure requested-section coverage and structural consistency, not visual truth."""
    if task not in _ANALYSIS_TASK_LABELS:
        raise ValueError('Unknown reference analysis task.')
    if not isinstance(description, str):
        raise ValueError('Reference analysis must be text.')
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    present, missing, duplicates = [], [], []
    for label in _ANALYSIS_TASK_LABELS[task]:
        matching = [line.split(':', 1)[1].strip() for line in lines
                    if line.upper().startswith(label + ':')]
        nonempty = [value for value in matching if value]
        if nonempty:
            present.append(label)
        else:
            missing.append(label)
        if len(matching) > 1:
            duplicates.append(label)
    total = len(_ANALYSIS_TASK_LABELS[task])
    score = round(len(present) / total * 100) if total else 100
    status = 'ready' if not missing and not duplicates and lines else ('partial' if lines else 'failed')
    return {
        'task': task, 'status': status, 'coverage_score': score,
        'present_sections': present, 'missing_sections': missing,
        'duplicate_sections': duplicates, 'review_required': status != 'ready',
    }

def build_studio_intelligence(payload: Mapping[str, Any], form: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the deterministic analysis contract for a validated Studio request."""
    if not isinstance(payload, Mapping) or payload.get("workspace") != "vision_studio":
        raise ValueError("Vision Studio request is required.")
    if not isinstance(form, Mapping):
        raise ValueError("Studio directives must be a mapping.")
    refs = payload.get("references", [])
    if not isinstance(refs, list):
        raise ValueError("Studio references must be a list.")
    roles = {ref.get("role") for ref in refs if isinstance(ref, Mapping)}
    options = payload.get("options", {})
    if not isinstance(options, Mapping):
        raise ValueError("Studio options must be an object.")
    output = options.get("output", "full")
    if output not in {"full", "raw"}:
        raise ValueError("Studio output must be full or raw.")
    if output == "raw" and "look" not in roles:
        raise ValueError("RAW output requires a Look reference.")
    if output == "full" and not roles.intersection({"look", "outfit"}):
        raise ValueError("Master Prompt requires a Look or Outfit reference.")

    manifest = []
    for role in ("look", "outfit"):
        if role in roles and not (output == "raw" and role == "outfit"):
            ref = next(item for item in refs if isinstance(item, Mapping) and item.get("role") == role)
            manifest.append({
                "role": role, "reference_id": ref.get("reference_id"),
                "analysis_scope": list(_REFERENCE_RULES[role]["analyze"]),
                "excluded_scope": list(_REFERENCE_RULES[role]["ignore"]),
            })

    directives = {}
    for field, key, replaces in _DIRECTIVE_FIELDS:
        value = form.get(field, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError(f"{field} must be text.")
        value = value.strip()
        if len(value) > MAX_DIRECTIVE_CHARS:
            raise ValueError(f"{field} exceeds {MAX_DIRECTIVE_CHARS} characters.")
        if value:
            directives[key] = {
                "value": value, "priority": "explicit_user_override", "replaces": replaces,
            }

    warnings: List[str] = []
    if "outfit" in directives and "outfit" in roles and output == "full":
        warnings.append(
            "Outfit Text Override takes priority over Outfit Reference garment details. "
            "Review intentional differences before generation."
        )
    if output == "raw":
        warnings.append("RAW mode uses Look analysis only; Outfit Reference is excluded.")

    return {
        "workspace": "vision_studio", "schema_version": "1.1",
        "output": output, "detail": options.get("detail", "balanced"),
        "reference_manifest": manifest, "creative_directives": directives,
        "priority_policy": {"ordered_sources": ["explicit_user_directives", "outfit_reference_for_garments", "look_reference_for_pose_environment_lighting_framing", "ai_inferred_suggestions"], "ai_suggestions_are_non_authoritative": True, "identity_source": "designated_subject_reference_only", "rules": ["Explicit user instructions always win over inferred visual details and AI suggestions.", "Outfit Reference controls garment construction, fabric, colour and embellishment unless an Outfit Text Override is supplied.", "Outfit Text Override replaces conflicting Outfit Reference garment details; never merge incompatible garment identities.", "Look Reference controls pose, gaze, framing, environment, lighting and camera; incidental Look clothing does not override Outfit Reference.", "When sources cannot be reconciled, preserve the higher-priority source and report the conflict."]},
        "identity_preservation": {
            "enabled": True,
            "rule": "Preserve the subject identity from the designated subject reference; never infer identity from Look or Outfit references.",
        },
        "smart_framing": {
            "enabled": True,
            "rule": "Describe only body regions and objects within the Look reference visible range; do not invent cropped or hidden anatomy.",
        },
        "fabric_physics": {
            "enabled": True,
            "rules": [
                "Respect garment weight, weave, thickness and natural gravity.",
                "Describe folds, pleats, drape, contact shadows and tension only where visually supported.",
                "Avoid floating, rigid, shrink-wrapped or implausibly stretched fabric.",
                "Do not force body shape or fabric behaviour that contradicts explicit user instructions.",
            ],
        },
        "visual_analysis_status": "pending_provider_analysis", "warnings": warnings,
    }



def build_studio_analysis_report(intelligence: Mapping[str, Any], look_description: str = "",
                                 outfit_description: str = "",
                                 analysis_errors: Mapping[str, str] | None = None) -> Dict[str, Any]:
    """Summarize provider-returned analysis and report complete reference coverage, not accuracy."""
    if not isinstance(intelligence, Mapping) or intelligence.get("workspace") != "vision_studio":
        raise ValueError("Valid Vision Studio intelligence is required.")
    look_text = look_description.strip() if isinstance(look_description, str) else ""
    outfit_text = outfit_description.strip() if isinstance(outfit_description, str) else ""
    errors = analysis_errors if isinstance(analysis_errors, Mapping) else {}
    manifest = intelligence.get("reference_manifest", [])
    roles = {item.get("role") for item in manifest if isinstance(item, Mapping)}
    expected = [role for role in ("look", "outfit") if role in roles]
    descriptions = {"look": look_text, "outfit": outfit_text}
    role_status = {}
    for role in ("look", "outfit"):
        role_errors = [str(message) for key, message in errors.items()
                       if str(key).startswith(role + "_") or str(key) == role]
        if role not in roles:
            role_status[role] = "excluded" if role == "outfit" and intelligence.get("output") == "raw" else "not_used"
        elif descriptions[role] and role_errors:
            role_status[role] = "partial"
        elif descriptions[role]:
            role_status[role] = "ready"
        else:
            role_status[role] = "failed"
    completed = sum(role_status[role] == "ready" for role in expected)
    usable = sum(bool(descriptions[role]) for role in expected)
    score = 0 if not expected else round(completed / len(expected) * 100)
    status = ("ready" if expected and completed == len(expected)
              else ("partial" if usable else "failed"))
    warnings = list(intelligence.get("warnings", []))
    conflicts = [item for item in warnings if "takes priority" in item.lower() or "conflict" in item.lower()]
    notes = [item for item in warnings if item not in conflicts]
    notes.extend(str(message) for message in errors.values())
    resolution = []
    if intelligence.get("creative_directives", {}).get("outfit") and "outfit" in roles:
        resolution.append({
            "type": "explicit_override", "sources": ["outfit_text_override", "outfit_reference"],
            "winner": "outfit_text_override", "status": "resolved",
            "explanation": "Your Outfit Text Override replaces conflicting garment details from the Outfit Reference. Incompatible garment identities are not blended.",
            "action": "Review the override text if you intended to retain any reference garment details.",
        })
    elif "look" in roles and "outfit" in roles:
        resolution.append({
            "type": "reference_scope", "sources": ["look_reference", "outfit_reference"],
            "winner": "outfit_reference_for_garments", "status": "policy_applied",
            "explanation": "Outfit Reference controls garment and fabric details. Look Reference controls pose, gaze, framing, environment, lighting and camera. Incidental Look clothing is contextual only.",
            "action": "No action is needed unless you intended Look clothing to replace the Outfit reference.",
        })
    if intelligence.get("creative_directives", {}).get("additional_instructions"):
        resolution.append({
            "type": "explicit_user_priority", "sources": ["additional_instructions", "reference_inference", "ai_suggestions"],
            "winner": "additional_instructions", "status": "priority_applied",
            "explanation": "Additional Creative Instructions outrank inferred reference details and AI suggestions.",
            "action": "Review the final prompt to confirm the instruction is represented.",
        })
    return {
        "status": status,
        "coverage_score": score,
        "score_label": "complete reference coverage",
        "score_note": "Percentage of selected references with complete usable analysis; it does not measure image accuracy. Partial or failed provider steps are shown separately.",
        "references": {
            "look": {"status": role_status["look"], "summary": look_text},
            "outfit": {"status": role_status["outfit"], "summary": outfit_text},
        },
        "conflicts": conflicts,
        "conflict_resolution": resolution,
        "notes": notes,
        "review_required": bool(conflicts or notes or status != "ready"),
    }

def build_studio_prompt_context(intelligence: Mapping[str, Any]) -> str:
    """Render guardrails and user overrides as explicit model instructions."""
    if not isinstance(intelligence, Mapping) or intelligence.get("workspace") != "vision_studio":
        raise ValueError("Valid Vision Studio intelligence is required.")
    lines = [
        "VISION STUDIO INTELLIGENCE CONTRACT:",
        "- Treat Look and Outfit as separate evidence sources; obey only each source's declared analysis scope.",
        "- Never copy facial identity from Look or Outfit. Preserve identity only from the designated subject reference and explicit identity-preservation instruction.",
        "- Smart framing: mention only body parts, clothing and objects inside the Look reference visible range; do not invent cropped anatomy or unseen footwear.",
        "- Fabric physics: preserve real garment weight, weave, gravity, folds, pleats, drape, contact shadows and plausible tension. Avoid floating, rigid or shrink-wrapped cloth.",
        "- Explicit user directives outrank inferred reference details and all AI suggestions. Never silently rewrite or discard them.",
        "- Garment priority: Outfit Text Override (if supplied) > Outfit Reference > incidental clothing in Look Reference.",
        "- Look Reference controls pose, gaze, framing, environment, lighting and camera; Outfit Reference controls garment construction, fabric, colour and embellishment.",
        "- If sources cannot be reconciled, preserve the higher-priority source and report the conflict; never blend incompatible garment identities.",
        "- Keep each fact in its correct prompt section and avoid duplicate descriptions.",
    ]
    for item in intelligence.get("reference_manifest", []):
        role = item.get("role", "").upper()
        lines.append(f"{role} REFERENCE MAY INFORM: " + "; ".join(item.get("analysis_scope", [])) + ".")
        lines.append(f"{role} REFERENCE MUST NOT INFORM: " + "; ".join(item.get("excluded_scope", [])) + ".")
    for key, item in intelligence.get("creative_directives", {}).items():
        lines.append(f"EXPLICIT OVERRIDE ({key}): {item['value']}")
    for warning in intelligence.get("warnings", []):
        lines.append("REVIEW: " + warning)
    if intelligence.get("output") == "raw":
        lines.extend([
            "RAW OUTPUT CONTRACT: do not generate a garment description or footwear section.",
            "The system supplies the fixed OUTFIT line, fabric-physics block and jewellery/accessory handling.",
        ])
    return "\n".join(lines)


def _directive_coverage(expected: str, actual: str) -> float:
    import re
    ignored = {"the", "and", "for", "with", "from", "that", "this", "keep", "make", "use", "only"}
    tokens = {word for word in re.findall(r"[a-z0-9]+", expected.lower())
              if len(word) > 2 and word not in ignored}
    if not tokens:
        return 1.0
    present = set(re.findall(r"[a-z0-9]+", actual.lower()))
    return len(tokens & present) / len(tokens)


def validate_studio_prompt(prompt: str, intelligence: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate prompt structure and whether explicit directives survive synthesis."""
    if not isinstance(prompt, str):
        raise ValueError("Generated Studio prompt must be text.")
    if not isinstance(intelligence, Mapping) or intelligence.get("workspace") != "vision_studio":
        raise ValueError("Valid Vision Studio intelligence is required.")
    allowed = {
        "SUBJECT PHYSIQUE", "HAIRSTYLE", "MAKEUP", "OUTFIT",
        "JEWELLERY AND ACCESSORIES", "POSE AND ACTION", "AND GAZE",
        "BACKGROUND AND ENVIRONMENT", "LIGHTING AND CAMERA",
        "COMPOSITION", "QUALITY", "NEGATIVE PROMPT",
    }
    sections, counts, active = {}, {}, None
    for line in prompt.splitlines():
        if ":" in line:
            label, value = line.split(":", 1)
            normalized = label.strip().upper()
            if normalized in allowed:
                active = normalized
                counts[active] = counts.get(active, 0) + 1
                sections[active] = (sections.get(active, "") + " " + value.strip()).strip()
                continue
        if active and line.strip():
            sections[active] = (sections.get(active, "") + " " + line.strip()).strip()

    warnings, suggestions, directive_checks = [], [], {}
    if not prompt.strip():
        warnings.append("Generated prompt is empty.")
    if not sections:
        warnings.append("No recognized prompt sections were found.")
    duplicates = sorted(label for label, count in counts.items() if count > 1)
    if duplicates:
        warnings.append("Duplicate prompt sections found: " + ", ".join(duplicates) + ".")
        suggestions.append("Combine repeated section content so each section appears once.")
    empty = sorted(label for label, value in sections.items() if not value.strip())
    if empty:
        warnings.append("Empty prompt sections found: " + ", ".join(empty) + ".")

    directives = intelligence.get("creative_directives", {})
    section_for = {
        "subject_physique": "SUBJECT PHYSIQUE", "hairstyle": "HAIRSTYLE",
        "pose_action": "POSE AND ACTION", "outfit": "OUTFIT",
    }
    for key, directive in directives.items():
        expected = directive.get("value", "") if isinstance(directive, Mapping) else ""
        if not expected:
            continue
        actual = prompt if key == "additional_instructions" else sections.get(section_for.get(key, ""), "")
        coverage = _directive_coverage(expected, actual)
        directive_checks[key] = {
            "status": "matched" if coverage >= 0.70 else "review_required",
            "coverage": round(coverage, 2),
        }
        if coverage < 0.70:
            label = section_for.get(key, "the prompt")
            warnings.append(f"Explicit {key.replace('_', ' ')} directive may not be preserved in {label}.")
            suggestions.append(f"Review the {label} section against the original instruction.")

    if intelligence.get("output") == "raw":
        outfit = sections.get("OUTFIT", "").lower()
        if "take the outfit from reference image" not in outfit:
            warnings.append("RAW OUTFIT section differs from the fixed system line; review before use.")
        if any(term in prompt.lower() for term in ("footwear", "shoes", "sandals")):
            warnings.append("RAW prompt may contain footwear despite the RAW exclusion rule.")
            suggestions.append("Remove footwear details from RAW output.")
    elif "outfit" in sections and not sections["outfit"].strip():
        warnings.append("Master Prompt contains an empty OUTFIT section.")
    elif any(item.get("role") == "outfit" for item in intelligence.get("reference_manifest", [])) and "OUTFIT" not in sections:
        warnings.append("An Outfit reference was selected but the Master Prompt has no OUTFIT section.")
        suggestions.append("Review whether the selected garment and fabric details were included.")

    passed = not warnings
    integrity = ("preserved" if directive_checks and all(
        item["status"] == "matched" for item in directive_checks.values()
    ) else ("review_required" if directive_checks else "not_applicable"))
    return {
        "passed": passed, "status": "ready" if passed else "needs_review",
        "warnings": warnings, "suggestions": suggestions,
        "section_count": len(sections), "sections": sorted(sections),
        "directive_checks": directive_checks, "instruction_integrity": integrity,
        "rewritten": False,
    }

def build_studio_intelligence(payload: Mapping[str, Any], form: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the deterministic analysis contract for a validated Studio request."""
    if not isinstance(payload, Mapping) or payload.get("workspace") != "vision_studio":
        raise ValueError("Vision Studio request is required.")
    if not isinstance(form, Mapping):
        raise ValueError("Studio directives must be a mapping.")
    refs = payload.get("references", [])
    if not isinstance(refs, list):
        raise ValueError("Studio references must be a list.")
    roles = {ref.get("role") for ref in refs if isinstance(ref, Mapping)}
    options = payload.get("options", {})
    if not isinstance(options, Mapping):
        raise ValueError("Studio options must be an object.")
    output = options.get("output", "full")
    if output not in {"full", "raw"}:
        raise ValueError("Studio output must be full or raw.")
    if output == "raw" and "look" not in roles:
        raise ValueError("RAW output requires a Look reference.")
    if output == "full" and not roles.intersection({"look", "outfit"}):
        raise ValueError("Master Prompt requires a Look or Outfit reference.")

    manifest = []
    for role in ("look", "outfit"):
        if role in roles and not (output == "raw" and role == "outfit"):
            ref = next(item for item in refs if isinstance(item, Mapping) and item.get("role") == role)
            manifest.append({
                "role": role, "reference_id": ref.get("reference_id"),
                "analysis_scope": list(_REFERENCE_RULES[role]["analyze"]),
                "excluded_scope": list(_REFERENCE_RULES[role]["ignore"]),
            })

    directives = {}
    for field, key, replaces in _DIRECTIVE_FIELDS:
        value = form.get(field, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError(f"{field} must be text.")
        value = value.strip()
        if len(value) > MAX_DIRECTIVE_CHARS:
            raise ValueError(f"{field} exceeds {MAX_DIRECTIVE_CHARS} characters.")
        if value:
            directives[key] = {
                "value": value, "priority": "explicit_user_override", "replaces": replaces,
            }

    warnings: List[str] = []
    if "outfit" in directives and "outfit" in roles and output == "full":
        warnings.append(
            "Outfit Text Override takes priority over Outfit Reference garment details. "
            "Review intentional differences before generation."
        )
    if output == "raw":
        warnings.append("RAW mode uses Look analysis only; Outfit Reference is excluded.")

    return {
        "workspace": "vision_studio", "schema_version": "1.1",
        "output": output, "detail": options.get("detail", "balanced"),
        "reference_manifest": manifest, "creative_directives": directives,
        "priority_policy": {"ordered_sources": ["explicit_user_directives", "outfit_reference_for_garments", "look_reference_for_pose_environment_lighting_framing", "ai_inferred_suggestions"], "ai_suggestions_are_non_authoritative": True, "identity_source": "designated_subject_reference_only", "rules": ["Explicit user instructions always win over inferred visual details and AI suggestions.", "Outfit Reference controls garment construction, fabric, colour and embellishment unless an Outfit Text Override is supplied.", "Outfit Text Override replaces conflicting Outfit Reference garment details; never merge incompatible garment identities.", "Look Reference controls pose, gaze, framing, environment, lighting and camera; incidental Look clothing does not override Outfit Reference.", "When sources cannot be reconciled, preserve the higher-priority source and report the conflict."]},
        "identity_preservation": {
            "enabled": True,
            "rule": "Preserve the subject identity from the designated subject reference; never infer identity from Look or Outfit references.",
        },
        "smart_framing": {
            "enabled": True,
            "rule": "Describe only body regions and objects within the Look reference visible range; do not invent cropped or hidden anatomy.",
        },
        "fabric_physics": {
            "enabled": True,
            "rules": [
                "Respect garment weight, weave, thickness and natural gravity.",
                "Describe folds, pleats, drape, contact shadows and tension only where visually supported.",
                "Avoid floating, rigid, shrink-wrapped or implausibly stretched fabric.",
                "Do not force body shape or fabric behaviour that contradicts explicit user instructions.",
            ],
        },
        "visual_analysis_status": "pending_provider_analysis", "warnings": warnings,
    }



def build_studio_analysis_report(intelligence: Mapping[str, Any], look_description: str = "",
                                 outfit_description: str = "",
                                 analysis_errors: Mapping[str, str] | None = None) -> Dict[str, Any]:
    """Summarize provider-returned analysis and report complete reference coverage, not accuracy."""
    if not isinstance(intelligence, Mapping) or intelligence.get("workspace") != "vision_studio":
        raise ValueError("Valid Vision Studio intelligence is required.")
    look_text = look_description.strip() if isinstance(look_description, str) else ""
    outfit_text = outfit_description.strip() if isinstance(outfit_description, str) else ""
    errors = analysis_errors if isinstance(analysis_errors, Mapping) else {}
    manifest = intelligence.get("reference_manifest", [])
    roles = {item.get("role") for item in manifest if isinstance(item, Mapping)}
    expected = [role for role in ("look", "outfit") if role in roles]
    descriptions = {"look": look_text, "outfit": outfit_text}
    role_status = {}
    for role in ("look", "outfit"):
        role_errors = [str(message) for key, message in errors.items()
                       if str(key).startswith(role + "_") or str(key) == role]
        if role not in roles:
            role_status[role] = "excluded" if role == "outfit" and intelligence.get("output") == "raw" else "not_used"
        elif descriptions[role] and role_errors:
            role_status[role] = "partial"
        elif descriptions[role]:
            role_status[role] = "ready"
        else:
            role_status[role] = "failed"
    completed = sum(role_status[role] == "ready" for role in expected)
    usable = sum(bool(descriptions[role]) for role in expected)
    score = 0 if not expected else round(completed / len(expected) * 100)
    status = ("ready" if expected and completed == len(expected)
              else ("partial" if usable else "failed"))
    warnings = list(intelligence.get("warnings", []))
    conflicts = [item for item in warnings if "takes priority" in item.lower() or "conflict" in item.lower()]
    notes = [item for item in warnings if item not in conflicts]
    notes.extend(str(message) for message in errors.values())
    resolution = []
    if intelligence.get("creative_directives", {}).get("outfit") and "outfit" in roles:
        resolution.append({
            "type": "explicit_override", "sources": ["outfit_text_override", "outfit_reference"],
            "winner": "outfit_text_override", "status": "resolved",
            "explanation": "Your Outfit Text Override replaces conflicting garment details from the Outfit Reference. Incompatible garment identities are not blended.",
            "action": "Review the override text if you intended to retain any reference garment details.",
        })
    elif "look" in roles and "outfit" in roles:
        resolution.append({
            "type": "reference_scope", "sources": ["look_reference", "outfit_reference"],
            "winner": "outfit_reference_for_garments", "status": "policy_applied",
            "explanation": "Outfit Reference controls garment and fabric details. Look Reference controls pose, gaze, framing, environment, lighting and camera. Incidental Look clothing is contextual only.",
            "action": "No action is needed unless you intended Look clothing to replace the Outfit reference.",
        })
    if intelligence.get("creative_directives", {}).get("additional_instructions"):
        resolution.append({
            "type": "explicit_user_priority", "sources": ["additional_instructions", "reference_inference", "ai_suggestions"],
            "winner": "additional_instructions", "status": "priority_applied",
            "explanation": "Additional Creative Instructions outrank inferred reference details and AI suggestions.",
            "action": "Review the final prompt to confirm the instruction is represented.",
        })
    return {
        "status": status,
        "coverage_score": score,
        "score_label": "complete reference coverage",
        "score_note": "Percentage of selected references with complete usable analysis; it does not measure image accuracy. Partial or failed provider steps are shown separately.",
        "references": {
            "look": {"status": role_status["look"], "summary": look_text},
            "outfit": {"status": role_status["outfit"], "summary": outfit_text},
        },
        "conflicts": conflicts,
        "conflict_resolution": resolution,
        "notes": notes,
        "review_required": bool(conflicts or notes or status != "ready"),
    }

def build_studio_prompt_context(intelligence: Mapping[str, Any]) -> str:
    """Render guardrails and user overrides as explicit model instructions."""
    if not isinstance(intelligence, Mapping) or intelligence.get("workspace") != "vision_studio":
        raise ValueError("Valid Vision Studio intelligence is required.")
    lines = [
        "VISION STUDIO INTELLIGENCE CONTRACT:",
        "- Treat Look and Outfit as separate evidence sources; obey only each source's declared analysis scope.",
        "- Never copy facial identity from Look or Outfit. Preserve identity only from the designated subject reference and explicit identity-preservation instruction.",
        "- Smart framing: mention only body parts, clothing and objects inside the Look reference visible range; do not invent cropped anatomy or unseen footwear.",
        "- Fabric physics: preserve real garment weight, weave, gravity, folds, pleats, drape, contact shadows and plausible tension. Avoid floating, rigid or shrink-wrapped cloth.",
        "- Explicit user directives outrank inferred reference details and all AI suggestions. Never silently rewrite or discard them.",
        "- Garment priority: Outfit Text Override (if supplied) > Outfit Reference > incidental clothing in Look Reference.",
        "- Look Reference controls pose, gaze, framing, environment, lighting and camera; Outfit Reference controls garment construction, fabric, colour and embellishment.",
        "- If sources cannot be reconciled, preserve the higher-priority source and report the conflict; never blend incompatible garment identities.",
        "- Keep each fact in its correct prompt section and avoid duplicate descriptions.",
    ]
    for item in intelligence.get("reference_manifest", []):
        role = item.get("role", "").upper()
        lines.append(f"{role} REFERENCE MAY INFORM: " + "; ".join(item.get("analysis_scope", [])) + ".")
        lines.append(f"{role} REFERENCE MUST NOT INFORM: " + "; ".join(item.get("excluded_scope", [])) + ".")
    for key, item in intelligence.get("creative_directives", {}).items():
        lines.append(f"EXPLICIT OVERRIDE ({key}): {item['value']}")
    for warning in intelligence.get("warnings", []):
        lines.append("REVIEW: " + warning)
    if intelligence.get("output") == "raw":
        lines.extend([
            "RAW OUTPUT CONTRACT: do not generate a garment description or footwear section.",
            "The system supplies the fixed OUTFIT line, fabric-physics block and jewellery/accessory handling.",
        ])
    return "\n".join(lines)


def _directive_coverage(expected: str, actual: str) -> float:
    import re
    ignored = {"the", "and", "for", "with", "from", "that", "this", "keep", "make", "use", "only"}
    tokens = {word for word in re.findall(r"[a-z0-9]+", expected.lower())
              if len(word) > 2 and word not in ignored}
    if not tokens:
        return 1.0
    present = set(re.findall(r"[a-z0-9]+", actual.lower()))
    return len(tokens & present) / len(tokens)


def validate_studio_prompt(prompt: str, intelligence: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate prompt structure and whether explicit directives survive synthesis."""
    if not isinstance(prompt, str):
        raise ValueError("Generated Studio prompt must be text.")
    if not isinstance(intelligence, Mapping) or intelligence.get("workspace") != "vision_studio":
        raise ValueError("Valid Vision Studio intelligence is required.")
    allowed = {
        "SUBJECT PHYSIQUE", "HAIRSTYLE", "MAKEUP", "OUTFIT",
        "JEWELLERY AND ACCESSORIES", "POSE AND ACTION", "AND GAZE",
        "BACKGROUND AND ENVIRONMENT", "LIGHTING AND CAMERA",
        "COMPOSITION", "QUALITY", "NEGATIVE PROMPT",
    }
    sections, counts, active = {}, {}, None
    for line in prompt.splitlines():
        if ":" in line:
            label, value = line.split(":", 1)
            normalized = label.strip().upper()
            if normalized in allowed:
                active = normalized
                counts[active] = counts.get(active, 0) + 1
                sections[active] = (sections.get(active, "") + " " + value.strip()).strip()
                continue
        if active and line.strip():
            sections[active] = (sections.get(active, "") + " " + line.strip()).strip()

    warnings, suggestions, directive_checks = [], [], {}
    if not prompt.strip():
        warnings.append("Generated prompt is empty.")
    if not sections:
        warnings.append("No recognized prompt sections were found.")
    duplicates = sorted(label for label, count in counts.items() if count > 1)
    if duplicates:
        warnings.append("Duplicate prompt sections found: " + ", ".join(duplicates) + ".")
        suggestions.append("Combine repeated section content so each section appears once.")
    empty = sorted(label for label, value in sections.items() if not value.strip())
    if empty:
        warnings.append("Empty prompt sections found: " + ", ".join(empty) + ".")

    directives = intelligence.get("creative_directives", {})
    section_for = {
        "subject_physique": "SUBJECT PHYSIQUE", "hairstyle": "HAIRSTYLE",
        "pose_action": "POSE AND ACTION", "outfit": "OUTFIT",
    }
    for key, directive in directives.items():
        expected = directive.get("value", "") if isinstance(directive, Mapping) else ""
        if not expected:
            continue
        actual = prompt if key == "additional_instructions" else sections.get(section_for.get(key, ""), "")
        coverage = _directive_coverage(expected, actual)
        directive_checks[key] = {
            "status": "matched" if coverage >= 0.70 else "review_required",
            "coverage": round(coverage, 2),
        }
        if coverage < 0.70:
            label = section_for.get(key, "the prompt")
            warnings.append(f"Explicit {key.replace('_', ' ')} directive may not be preserved in {label}.")
            suggestions.append(f"Review the {label} section against the original instruction.")

    if intelligence.get("output") == "raw":
        outfit = sections.get("OUTFIT", "").lower()
        if "take the outfit from reference image" not in outfit:
            warnings.append("RAW OUTFIT section differs from the fixed system line; review before use.")
        if any(term in prompt.lower() for term in ("footwear", "shoes", "sandals")):
            warnings.append("RAW prompt may contain footwear despite the RAW exclusion rule.")
            suggestions.append("Remove footwear details from RAW output.")
    elif "outfit" in sections and not sections["outfit"].strip():
        warnings.append("Master Prompt contains an empty OUTFIT section.")
    elif any(item.get("role") == "outfit" for item in intelligence.get("reference_manifest", [])) and "OUTFIT" not in sections:
        warnings.append("An Outfit reference was selected but the Master Prompt has no OUTFIT section.")
        suggestions.append("Review whether the selected garment and fabric details were included.")

    passed = not warnings
    integrity = ("preserved" if directive_checks and all(
        item["status"] == "matched" for item in directive_checks.values()
    ) else ("review_required" if directive_checks else "not_applicable"))
    return {
        "passed": passed, "status": "ready" if passed else "needs_review",
        "warnings": warnings, "suggestions": suggestions,
        "section_count": len(sections), "sections": sorted(sections),
        "directive_checks": directive_checks, "instruction_integrity": integrity,
        "rewritten": False,
    }
