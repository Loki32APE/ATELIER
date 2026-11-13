"""Input validation for the shared Atelier workspace request envelope."""

from collections.abc import Mapping
from typing import Any, Dict, List

from .schemas import (
    SUPPORTED_IMAGE_MIME_TYPES,
    SUPPORTED_WORKSPACES,
    ImageReference,
    ValidationResult,
    WorkspaceRequest,
)
from .workspaces import get_workspace_policy


def validate_workspace_request(payload: Any) -> ValidationResult:
    """Validate and normalize a request without making network or AI calls.

    Expected shape:
        {
            "workspace": "vision_lab" | "vision_studio",
            "instructions": "optional text",
            "references": [
                {"reference_id": "ref-1", "role": "look",
                 "mime_type": "image/jpeg", "filename": "look.jpg"}
            ],
            "options": {}
        }

    Vision Lab is text-only and rejects all image references. Vision Studio
    accepts reference metadata according to its workspace policy. Actual
    upload bytes must be validated by the upload boundary.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(payload, Mapping):
        return ValidationResult(False, ("Request must be a JSON object.",))

    workspace = payload.get("workspace")
    if not isinstance(workspace, str) or workspace not in SUPPORTED_WORKSPACES:
        errors.append("Workspace must be 'vision_lab' or 'vision_studio'.")
        policy = None
    else:
        policy = get_workspace_policy(workspace)

    instructions = payload.get("instructions", "")
    if not isinstance(instructions, str):
        errors.append("Instructions must be text.")
    elif len(instructions) > 20_000:
        errors.append("Instructions must be 20000 characters or fewer.")

    options = payload.get("options", {})
    if not isinstance(options, Mapping):
        errors.append("Options must be an object.")

    references = payload.get("references", [])
    if not isinstance(references, list):
        errors.append("References must be a list.")
        references = []

    if workspace == "vision_lab" and references:
        errors.append(
            "Vision Lab is text-only and does not accept image references; "
            "use Vision Studio for image references."
        )

    seen_ids = set()
    for index, reference in enumerate(references):
        prefix = f"Reference {index + 1}"
        if not isinstance(reference, Mapping):
            errors.append(f"{prefix} must be an object.")
            continue

        reference_id = reference.get("reference_id")
        role = reference.get("role")
        mime_type = reference.get("mime_type")

        if not isinstance(reference_id, str) or not reference_id.strip():
            errors.append(f"{prefix} needs a non-empty reference_id.")
        elif reference_id in seen_ids:
            errors.append(f"Duplicate reference_id: {reference_id}.")
        else:
            seen_ids.add(reference_id)

        if policy is not None and role not in policy.allowed_reference_roles:
            errors.append(
                f"{prefix} role '{role}' is not supported in {policy.display_name}."
            )
        if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
            errors.append(f"{prefix} has an unsupported image MIME type.")

        filename = reference.get("filename")
        if filename is not None and not isinstance(filename, str):
            errors.append(f"{prefix} filename must be text.")

    if policy is not None and policy.requires_reference and not references:
        errors.append(f"{policy.display_name} requires at least one reference image.")

    if workspace == "vision_lab" and not (instructions or "").strip():
        warnings.append("No instructions supplied; the workspace may need user input.")

    return ValidationResult(
        valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def normalize_workspace_request(payload: Dict[str, Any]) -> WorkspaceRequest:
    """Convert a previously validated payload into the typed request contract.

    Raises ValueError when the payload is invalid.
    """
    result = validate_workspace_request(payload)
    if not result.valid:
        raise ValueError("; ".join(result.errors))

    references = tuple(
        ImageReference(
            reference_id=item["reference_id"].strip(),
            role=item["role"],
            mime_type=item["mime_type"],
            filename=item.get("filename"),
        )
        for item in payload.get("references", [])
    )
    return WorkspaceRequest(
        workspace=payload["workspace"],
        instructions=payload.get("instructions", ""),
        references=references,
        options=dict(payload.get("options", {})),
    )
