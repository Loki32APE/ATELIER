"""Shared intelligence foundation for Atelier workspaces."""

from .schemas import (
    SUPPORTED_WORKSPACES,
    ImageReference,
    ValidationResult,
    WorkspaceRequest,
)
from .validation import validate_workspace_request
from .workspaces import WORKSPACE_POLICIES, WorkspacePolicy, get_workspace_policy
from .adapters import adapt_legacy_studio_request

__all__ = [
    "SUPPORTED_WORKSPACES",
    "ImageReference",
    "ValidationResult",
    "WorkspaceRequest",
    "WorkspacePolicy",
    "WORKSPACE_POLICIES",
    "get_workspace_policy",
    "validate_workspace_request",
    "adapt_legacy_studio_request",
]
