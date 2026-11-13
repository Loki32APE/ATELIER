import json
from pathlib import Path
import unittest
from unittest.mock import patch

from atelier_engine.vision_lab_pipeline import run_vision_lab_pipeline


class VisionLabPipelineTests(unittest.TestCase):
    def test_runs_deterministic_mode_without_provider(self):
        result = run_vision_lab_pipeline(
            {"instructions": "Keep the red jacket.", "selections": {"appearance_identity": {"subject": "adult person"}}},
            use_ai=False,
        )
        self.assertEqual(result["ai_status"], "not_requested")
        self.assertIn("Keep the red jacket.", result["prompt"])
        self.assertTrue(result["quality"]["passed"])

    @patch("atelier_engine.vision_lab_pipeline.chat_completion")
    def test_output_language_is_passed_to_provider_and_returned(self, completion):
        completion.return_value = {"content": "एक सुंदर चित्र।", "model": "mock/model"}
        result = run_vision_lab_pipeline({"language": "Hindi"}, model_id="mock/model")
        system_message = completion.call_args.args[0][0]["content"]
        self.assertIn("OUTPUT LANGUAGE:", system_message)
        self.assertIn("Hindi", system_message)
        self.assertEqual(result["output_language"], "Hindi")

    @patch("atelier_engine.vision_lab_pipeline.chat_completion")
    def test_ai_composition_preserves_protected_instruction(self, completion):
        completion.return_value = {"content": "A cinematic portrait. Keep the red jacket.", "model": "mock/model"}
        result = run_vision_lab_pipeline(
            {"instructions": "Keep the red jacket."},
            model_id="mock/model",
        )
        self.assertEqual(result["ai_status"], "completed")
        self.assertEqual(result["provider_model"], "mock/model")
        self.assertTrue(result["quality"]["passed"])


    @patch("atelier_engine.vision_lab_pipeline.chat_completion")
    def test_restores_selected_catalog_values_omitted_by_ai(self, completion):
        completion.return_value = {
            "content": "A cinematic editorial portrait with soft studio lighting and refined detail.",
            "model": "mock/model",
        }
        payload = {
            "mode": "advanced",
            "instructions": "Keep the original outfit unchanged.",
            "selections": {
                "outfit_styling": {"choices": {
                    "garment_type": "Sambalpuri saree",
                    "embroidery": ["Zari embroidery"],
                }},
                "poses_expressions": {"choices": {"pose": "Walking"}},
            },
        }
        result = run_vision_lab_pipeline(payload, model_id="mock/model")

        self.assertIn("Sambalpuri saree", result["prompt"])
        self.assertIn("Zari embroidery", result["prompt"])
        self.assertIn("Walking", result["prompt"])
        self.assertIn("Keep the original outfit unchanged.", result["prompt"])
        self.assertIn("Selected creative details retained from your brief:", result["prompt"])
        self.assertEqual(result["selection_coverage"]["selected_details_total"], 3)
        self.assertEqual(result["selection_coverage"]["selected_details_restored"], 3)
        self.assertTrue(result["selection_coverage"]["instruction_restored"])
        self.assertEqual(result["processing_status"], "needs_review")
        self.assertTrue(result["optimization_warnings"])


    @patch("atelier_engine.vision_lab_pipeline.chat_completion")
    def test_ai_output_retains_every_catalog_value_across_seven_modules(self, completion):
        catalog_path = Path(__file__).resolve().parents[1] / "static" / "Catalog" / "visual_lab" / "modules.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))["modules"]
        selections = {}
        expected_values = []

        for module_id, definition in catalog.items():
            choices = {}
            for mode in ("basic", "advanced"):
                for field in definition[mode]:
                    value = field["options"][0]
                    choices[field["id"]] = [value] if field["type"] == "multi" else value
                    expected_values.append(value)
            selections[module_id] = {"choices": choices}

        completion.return_value = {
            "content": "A cohesive editorial portrait with polished composition and natural light.",
            "model": "mock/model",
        }
        result = run_vision_lab_pipeline(
            {"mode": "advanced", "selections": selections},
            model_id="mock/model",
        )

        for value in expected_values:
            with self.subTest(selected_value=value):
                self.assertIn(value.casefold(), result["prompt"].casefold())
        self.assertEqual(
            result["selection_coverage"]["selected_details_total"],
            len(expected_values),
        )
        self.assertGreater(result["selection_coverage"]["selected_details_restored"], 0)
        self.assertEqual(result["processing_status"], "needs_review")

    @patch("atelier_engine.vision_lab_pipeline.chat_completion")
    def test_does_not_duplicate_selected_values_already_present_in_ai_prompt(self, completion):
        completion.return_value = {
            "content": "A portrait featuring a Sambalpuri saree while Walking. Keep the original outfit unchanged.",
            "model": "mock/model",
        }
        result = run_vision_lab_pipeline({
            "instructions": "Keep the original outfit unchanged.",
            "selections": {"outfit_styling": {"choices": {"garment_type": "Sambalpuri saree"}},
                           "poses_expressions": {"choices": {"pose": "Walking"}}},
        }, model_id="mock/model")

        self.assertEqual(result["selection_coverage"]["selected_details_restored"], 0)
        self.assertFalse(result["selection_coverage"]["instruction_restored"])
        self.assertEqual(result["processing_status"], "ready")
        self.assertNotIn("Selected creative details retained from your brief:", result["prompt"])

    @patch("atelier_engine.vision_lab_pipeline.chat_completion")
    def test_provider_receives_multiline_structured_context(self, completion):
        completion.return_value = {
            "content": "A detailed cinematic portrait with natural lighting.",
            "model": "mock/model",
        }
        run_vision_lab_pipeline({
            "selections": {"appearance_identity": {"choices": {"skin_tone": "Warm medium"}}}
        }, model_id="mock/model")
        user_message = completion.call_args.args[0][1]["content"]
        self.assertIn("\nMODULE SELECTIONS:", user_message)
        self.assertNotIn("\\nMODULE SELECTIONS:", user_message)

    @patch("atelier_engine.vision_lab_pipeline.chat_completion")
    def test_target_profile_does_not_replace_reasoning_provider_model(self, completion):
        completion.return_value = {"content": "A detailed portrait. Keep the red jacket.", "model": "reasoner/model"}
        result = run_vision_lab_pipeline(
            {"instructions": "Keep the red jacket."},
            model_id="reasoner/model",
            target_model_id="black-forest-labs/flux.1-pro",
        )
        self.assertEqual(result["provider_model"], "reasoner/model")
        self.assertEqual(result["model_profile"]["model_id"], "black-forest-labs/flux.1-pro")
        completion.assert_called_once()
        self.assertEqual(completion.call_args.kwargs["model_id"], "reasoner/model")

    @patch("atelier_engine.vision_lab_pipeline.chat_completion")
    def test_provider_failure_returns_labeled_deterministic_fallback(self, completion):
        completion.side_effect = RuntimeError("provider unavailable")
        result = run_vision_lab_pipeline({"instructions": "Keep the red jacket."})
        self.assertEqual(result["ai_status"], "failed")
        self.assertIn("Explicit user instructions", result["prompt"])
        self.assertEqual(result["processing_status"], "needs_review")

    @patch("atelier_engine.vision_lab_pipeline.chat_completion")
    def test_non_english_request_warns_when_provider_falls_back_to_english(self, completion):
        completion.side_effect = RuntimeError("provider unavailable")
        result = run_vision_lab_pipeline({"language": "Odia"}, model_id="mock/model")
        self.assertEqual(result["output_language"], "Odia")
        self.assertTrue(any("fallback remains in English" in item for item in result["optimization_warnings"]))
        self.assertEqual(result["processing_status"], "needs_review")

    def test_rejects_image_references(self):
        with self.assertRaisesRegex(ValueError, "text-only"):
            run_vision_lab_pipeline({"references": [{"role": "look"}]}, use_ai=False)

    @patch("atelier_engine.vision_lab_pipeline.chat_completion")
    def test_restores_selection_when_it_only_appears_inside_a_longer_word(self, completion):
        completion.return_value = {
            "content": "A portrait with a redesigned background and polished lighting.",
            "model": "mock/model",
        }
        result = run_vision_lab_pipeline(
            {"selections": {"outfit_styling": {"choices": {"garment_colour": "Red"}}}},
            model_id="mock/model",
        )

        self.assertIn("Garment colour: Red", result["prompt"])
        self.assertEqual(result["selection_coverage"]["selected_details_restored"], 1)
        self.assertEqual(result["processing_status"], "needs_review")


if __name__ == "__main__":
    unittest.main()
