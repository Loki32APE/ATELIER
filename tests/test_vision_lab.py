"""Tests for the structured, text-only Vision Lab draft boundary."""

import unittest

from atelier_engine.vision_lab import (
    VISION_LAB_MODULES,
    normalize_vision_lab_draft,
)


class VisionLabDraftTests(unittest.TestCase):
    def test_registers_all_seven_approved_modules(self):
        self.assertEqual(len(VISION_LAB_MODULES), 7)
        self.assertEqual(
            [key for key, _ in VISION_LAB_MODULES],
            [
                "appearance_identity", "outfit_styling", "poses_expressions",
                "themes_environment", "lighting_composition",
                "camera_photography", "output_rendering",
            ],
        )

    def test_normalizes_basic_draft_and_preserves_selections(self):
        draft = normalize_vision_lab_draft({
            "mode": "BASIC",
            "instructions": "  cinematic portrait  ",
            "selections": {
                "appearance_identity": {"subject": "adult woman"},
                "lighting_composition": ["soft window light", "eye-level framing"],
            },
        })
        self.assertEqual(draft.mode, "basic")
        self.assertEqual(draft.instructions, "cinematic portrait")
        self.assertEqual(draft.selections["appearance_identity"]["subject"], "adult woman")
        self.assertEqual(draft.selections["lighting_composition"][0], "soft window light")

    def test_accepts_supported_output_languages(self):
        for language in ("English", "Hindi", "Odia"):
            with self.subTest(language=language):
                draft = normalize_vision_lab_draft({"language": language})
                self.assertEqual(draft.language, language)

    def test_rejects_unsupported_output_language(self):
        with self.assertRaisesRegex(ValueError, "language must be"):
            normalize_vision_lab_draft({"language": "French"})

    def test_accepts_advanced_mode(self):
        draft = normalize_vision_lab_draft({"mode": "advanced"})
        self.assertEqual(draft.mode, "advanced")

    def test_rejects_image_references(self):
        with self.assertRaisesRegex(ValueError, "text-only"):
            normalize_vision_lab_draft({"references": [{"role": "look"}]})

    def test_rejects_image_fields(self):
        with self.assertRaisesRegex(ValueError, "does not accept image fields"):
            normalize_vision_lab_draft({"image": "data:image/png;base64,..."})

    def test_rejects_unknown_module(self):
        with self.assertRaisesRegex(ValueError, "Unknown Vision Lab module"):
            normalize_vision_lab_draft({"selections": {"reference_upload": {}}})

    def test_rejects_invalid_mode(self):
        with self.assertRaisesRegex(ValueError, "mode must be"):
            normalize_vision_lab_draft({"mode": "premium"})

    def test_rejects_non_text_instructions(self):
        with self.assertRaisesRegex(ValueError, "instructions must be text"):
            normalize_vision_lab_draft({"instructions": ["portrait"]})

    def test_rejects_non_finite_numeric_selection_values(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite number"):
                    normalize_vision_lab_draft({
                        "selections": {"camera_photography": {"exposure": value}}
                    })

    def test_rejects_non_json_selection_values(self):
        with self.assertRaisesRegex(ValueError, "must be an object, list, or text"):
            normalize_vision_lab_draft({"selections": {"camera_photography": object()}})

    def test_rejects_deeply_nested_selection_values(self):
        nested = {"a": {"b": {"c": {"d": {"e": {"f": "too deep"}}}}}}
        with self.assertRaisesRegex(ValueError, "nested too deeply"):
            normalize_vision_lab_draft({"selections": {"appearance_identity": nested}})


if __name__ == "__main__":
    unittest.main()
