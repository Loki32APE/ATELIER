"""Tests for workspace-specific Atelier intelligence policies."""

import unittest

from atelier_engine.validation import validate_workspace_request
from atelier_engine.workspaces import WORKSPACE_POLICIES, get_workspace_policy


def reference(role, reference_id="ref-1"):
    return {
        "reference_id": reference_id,
        "role": role,
        "mime_type": "image/jpeg",
    }


class WorkspacePolicyTests(unittest.TestCase):
    def test_vision_lab_does_not_require_reference(self):
        result = validate_workspace_request({
            "workspace": "vision_lab",
            "instructions": "Create a cinematic portrait.",
        })
        self.assertTrue(result.valid)

    def test_vision_lab_rejects_every_image_reference_role(self):
        for role in ("identity", "inspiration", "style", "other", "look", "outfit"):
            with self.subTest(role=role):
                result = validate_workspace_request({
                    "workspace": "vision_lab",
                    "instructions": "Create a portrait.",
                    "references": [reference(role)],
                })
                self.assertFalse(result.valid)
                self.assertTrue(any(
                    "Vision Lab is text-only" in error for error in result.errors
                ))

    def test_vision_studio_requires_reference(self):
        result = validate_workspace_request({"workspace": "vision_studio"})
        self.assertFalse(result.valid)
        self.assertTrue(any("requires at least one reference" in e for e in result.errors))

    def test_vision_studio_accepts_look_and_outfit_roles(self):
        result = validate_workspace_request({
            "workspace": "vision_studio",
            "references": [reference("look", "look-1"), reference("outfit", "outfit-1")],
        })
        self.assertTrue(result.valid)

    def test_policy_registry_has_both_independent_workspaces(self):
        self.assertEqual(set(WORKSPACE_POLICIES), {"vision_lab", "vision_studio"})
        lab = get_workspace_policy("vision_lab")
        studio = get_workspace_policy("vision_studio")
        self.assertFalse(lab.requires_reference)
        self.assertEqual(lab.allowed_reference_roles, frozenset())
        self.assertTrue(studio.requires_reference)
        self.assertIn("text-only", lab.description.lower())


if __name__ == "__main__":
    unittest.main()
