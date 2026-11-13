"""Workspace-specific policy for Atelier's shared intelligence foundation.

Vision Lab and Vision Studio share request contracts, but intentionally keep
separate reference rules so their workflows can evolve independently.
"""
from dataclasses import dataclass
from typing import FrozenSet, Mapping


@dataclass(frozen=True)
class WorkspacePolicy:
    """Validation and capability rules for one Atelier workspace."""

    workspace: str
    display_name: str
    requires_reference: bool
    allowed_reference_roles: FrozenSet[str]
    description: str


WORKSPACE_POLICIES: Mapping[str, WorkspacePolicy] = {
    "vision_lab": WorkspacePolicy(
        workspace="vision_lab",
        display_name="Vision Lab",
        requires_reference=False,
        allowed_reference_roles=frozenset(),
        description="Text-only creative construction. Image references are not accepted.",
    ),
    "vision_studio": WorkspacePolicy(
        workspace="vision_studio",
        display_name="Vision Studio",
        requires_reference=True,
        allowed_reference_roles=frozenset(
            {"look", "outfit", "identity", "style", "other"}
        ),
        description="Reference-led visual analysis and prompt synthesis.",
    ),
}


def get_workspace_policy(workspace: str) -> WorkspacePolicy:
    """Return a workspace policy or raise KeyError for an unknown workspace."""
    return WORKSPACE_POLICIES[workspace]
