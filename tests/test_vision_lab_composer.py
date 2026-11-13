"""Tests for the provider-neutral Vision Lab composer foundation."""
import json
from pathlib import Path
import unittest

from atelier_engine.vision_lab_composer import compose_vision_lab_prompt


class VisionLabComposerTests(unittest.TestCase):
    def test_composes_all_seven_modules_in_approved_order(self):
        keys = [
            "appearance_identity", "outfit_styling", "poses_expressions",
            "themes_environment", "lighting_composition",
            "camera_photography", "output_rendering",
        ]
        labels = [
            "Appearance & Identity", "Outfit & Styling", "Poses & Expressions",
            "Themes & Environment", "Lighting & Composition",
            "Camera & Photography", "Output & Rendering Intelligence",
        ]
        result = compose_vision_lab_prompt({
            "mode": "advanced",
            "selections": {key: {"description": key} for key in reversed(keys)},
        })
        self.assertEqual(result["included_modules"], keys)
        positions = [result["prompt"].index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))


    def test_composer_preserves_every_catalog_field_across_all_seven_modules(self):
        catalog_path = Path(__file__).resolve().parents[1] / "static" / "Catalog" / "visual_lab" / "modules.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))["modules"]
        selections = {}
        selected_values = []

        for module_id, definition in catalog.items():
            choices = {}
            for mode in ("basic", "advanced"):
                for field in definition[mode]:
                    value = field["options"][0]
                    choices[field["id"]] = [value] if field["type"] == "multi" else value
                    selected_values.append(value)
            selections[module_id] = {"choices": choices}

        result = compose_vision_lab_prompt({
            "mode": "advanced",
            "instructions": "Preserve every selected creative detail.",
            "selections": selections,
        })

        self.assertEqual(result["included_modules"], list(catalog))
        for value in selected_values:
            with self.subTest(selected_value=value):
                self.assertIn(value, result["prompt"])
        self.assertIn("Preserve every selected creative detail.", result["prompt"])
        self.assertEqual(result["instruction_integrity"], "preserved")


    def test_preserves_explicit_user_instructions_verbatim(self):
        instruction = "Keep the subject standing; do not change the outfit."
        result = compose_vision_lab_prompt({"instructions": instruction})
        self.assertIn("Explicit user instructions (preserve exactly):\n" + instruction, result["prompt"])
        self.assertEqual(result["instruction_integrity"], "preserved")

    def test_reports_conflicts_without_resolving_them(self):
        result = compose_vision_lab_prompt({"selections": {
            "appearance_identity": {"framing": "full-body"},
            "camera_photography": {"shot_type": "close-up"},
        }})
        self.assertEqual(result["processing_status"], "needs_review")
        self.assertIn("Review required before finalization", result["prompt"])
        self.assertIn("FRAMING_CONFLICT", [item["code"] for item in result["rule_findings"]])
        self.assertIn("full-body", result["prompt"])
        self.assertIn("close-up", result["prompt"])

    def test_reports_duplicates_without_dropping_content(self):
        repeated = "cinematic portrait"
        result = compose_vision_lab_prompt({
            "instructions": repeated,
            "selections": {"appearance_identity": {"description": repeated}},
        })
        self.assertEqual(result["duplicate_instructions"], [repeated])
        self.assertEqual(result["prompt"].count(repeated), 3)
        self.assertIn("Repeated details detected", result["prompt"])

    def test_supports_basic_and_advanced_modes(self):
        for mode in ("basic", "advanced"):
            with self.subTest(mode=mode):
                self.assertEqual(compose_vision_lab_prompt({"mode": mode})["mode"], mode)

    def test_output_is_deterministic(self):
        payload = {"selections": {
            "camera_photography": {"lens": "85mm", "framing": "portrait"},
            "appearance_identity": {"subject": "adult person"},
        }}
        self.assertEqual(compose_vision_lab_prompt(payload), compose_vision_lab_prompt(payload))

    def test_does_not_mutate_user_input(self):
        payload = {"instructions": "Preserve details.", "selections": {
            "appearance_identity": {"traits": ["natural", "realistic"]},
        }}
        before = {
            "instructions": "Preserve details.",
            "selections": {"appearance_identity": {"traits": ["natural", "realistic"]}},
        }
        compose_vision_lab_prompt(payload)
        self.assertEqual(payload, before)

    def test_renders_nested_selections_and_false_values(self):
        result = compose_vision_lab_prompt({"selections": {
            "output_rendering": {"high_resolution": True, "watermark": False},
        }})
        self.assertIn("High resolution: Yes", result["prompt"])
        self.assertIn("Watermark: No", result["prompt"])

    def test_rejects_image_references(self):
        with self.assertRaisesRegex(ValueError, "text-only"):
            compose_vision_lab_prompt({"references": [{"role": "look"}]})


if __name__ == "__main__":
    unittest.main()
