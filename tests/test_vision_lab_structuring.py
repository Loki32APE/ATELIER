"""Tests for the canonical Vision Lab structuring handoff."""
import unittest

from atelier_engine.vision_lab_structuring import (
    SCHEMA_VERSION,
    structure_vision_lab_payload,
)


class VisionLabStructuringTests(unittest.TestCase):
    def test_builds_canonical_payload(self):
        result = structure_vision_lab_payload({
            "mode": "ADVANCED",
            "instructions": "  Keep all explicit details.  ",
            "selections": {
                "lighting_composition": {"lighting": "soft daylight"},
                "appearance_identity": {"subject": "adult person"},
            },
        })
        self.assertEqual(result["workspace"], "vision_lab")
        self.assertEqual(result["schema_version"], SCHEMA_VERSION)
        self.assertEqual(result["mode"], "advanced")
        self.assertEqual(result["user_instructions"], "Keep all explicit details.")
        self.assertEqual(
            list(result["module_selections"]),
            ["appearance_identity", "lighting_composition"],
        )
        self.assertEqual(result["instruction_integrity"], "preserved")
        self.assertEqual(result["processing_status"], "ready")

    def test_preserves_all_seven_modules_when_supplied(self):
        keys = [
            "appearance_identity", "outfit_styling", "poses_expressions",
            "themes_environment", "lighting_composition",
            "camera_photography", "output_rendering",
        ]
        result = structure_vision_lab_payload({
            "selections": {key: {"enabled": True} for key in reversed(keys)}
        })
        self.assertEqual(list(result["module_selections"]), keys)

    def test_conflict_is_reported_and_requires_review(self):
        result = structure_vision_lab_payload({"selections": {
            "appearance_identity": {"framing": "full-body"},
            "camera_photography": {"shot_type": "close-up"},
        }})
        self.assertEqual(result["processing_status"], "needs_review")
        self.assertIn("FRAMING_CONFLICT", [item["code"] for item in result["rule_findings"]])

    def test_duplicate_text_is_reported_but_not_removed(self):
        text = "cinematic portrait"
        result = structure_vision_lab_payload({
            "instructions": text,
            "selections": {"appearance_identity": {"description": text}},
        })
        self.assertEqual(result["user_instructions"], text)
        self.assertEqual(result["module_selections"]["appearance_identity"]["description"], text)
        self.assertEqual(result["duplicate_instructions"], [text])
        self.assertEqual(result["processing_status"], "ready")

    def test_does_not_mutate_input(self):
        selections = {"camera_photography": {"framing": "full-body"}}
        original = {"camera_photography": {"framing": "full-body"}}
        structure_vision_lab_payload({"selections": selections})
        self.assertEqual(selections, original)

    def test_returns_independent_nested_selection_data(self):
        payload = {"selections": {"appearance_identity": {"details": ["one"]}}}
        result = structure_vision_lab_payload(payload)
        result["module_selections"]["appearance_identity"]["details"].append("two")
        self.assertEqual(payload["selections"]["appearance_identity"]["details"], ["one"])

    def test_output_is_deterministic(self):
        payload = {"mode": "basic", "selections": {
            "lighting_composition": {"lighting": "soft daylight"},
            "appearance_identity": {"framing": "full-body"},
        }}
        self.assertEqual(
            structure_vision_lab_payload(payload),
            structure_vision_lab_payload(payload),
        )

    def test_rejects_vision_lab_image_references(self):
        with self.assertRaisesRegex(ValueError, "text-only"):
            structure_vision_lab_payload({"references": [{"role": "look"}]})

    def test_rejects_invalid_payload(self):
        with self.assertRaisesRegex(ValueError, "mode must be"):
            structure_vision_lab_payload({"mode": "premium"})


if __name__ == "__main__":
    unittest.main()
