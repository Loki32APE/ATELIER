"""Small, provider-neutral data contracts shared by Atelier workspaces.

These contracts intentionally use the Python standard library so the core
engine does not depend on a particular AI provider or web framework.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

SUPPORTED_WORKSPACES = frozenset({"vision_lab", "vision_studio"})
SUPPORTED_IMAGE_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)


@dataclass(frozen=True)
class ImageReference:
    """Metadata for an uploaded reference; image bytes are handled separately."""

    reference_id: str
    role: str
    mime_type: str
    filename: Optional[str] = None


@dataclass(frozen=True)
class WorkspaceRequest:
    """Normalized request envelope accepted by the shared intelligence layer."""

    workspace: str
    instructions: str = ""
    references: Tuple[ImageReference, ...] = field(default_factory=tuple)
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    """Validation outcome; callers decide how errors are shown to users."""

    valid: bool
    errors: Tuple[str, ...] = field(default_factory=tuple)
    warnings: Tuple[str, ...] = field(default_factory=tuple)
