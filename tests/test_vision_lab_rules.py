"""Tests for deterministic Vision Lab rule evaluation."""

import unittest

from atelier_engine.vision_lab_rules import evaluate_vision_lab_rules


class VisionLabRuleTests(unittest.TestCase):
    def test_detects_framing_conflict_across_modules(self):
        report = evaluate_vision_lab_rules({"selections": {
            "appearance_identity": {"framing": "full-body"},
            "camera_photography": {"shot_type": "close-up"},
        }})
        self.assertIn("FRAMING_CONFLICT", [item.code for item in report.findings])
        self.assertTrue(report.has_conflicts)

    def test_detects_pose_conflict(self):
        report = evaluate_vision_lab_rules({"selections": {
            "poses_expressions": {"pose": "standing"},
            "appearance_identity": {"body_position": "sitting"},
        }})
        self.assertIn("POSE_CONFLICT", [item.code for item in report.findings])

    def test_detects_environment_conflict(self):
        report = evaluate_vision_lab_rules({"selections": {
            "themes_environment": {"setting": "indoor"},
            "lighting_composition": {"environment": "outdoor"},
        }})
        self.assertIn("ENVIRONMENT_CONFLICT", [item.code for item in report.findings])

    def test_compatible_values_do_not_warn(self):
        report = evaluate_vision_lab_rules({"selections": {
            "poses_expressions": {"pose": "standing"},
            "appearance_identity": {"pose": "standing"},
        }})
        self.assertFalse(report.has_conflicts)

    def test_detects_duplicate_text_without_removing_it(self):
        payload = {"instructions": "cinematic portrait", "selections": {
            "appearance_identity": {"description": "cinematic portrait"},
        }}
        report = evaluate_vision_lab_rules(payload)
        self.assertEqual(report.duplicate_instructions, ("cinematic portrait",))
        self.assertEqual(report.draft.instructions, "cinematic portrait")
        self.assertEqual(report.draft.selections["appearance_identity"]["description"], "cinematic portrait")

    def test_preserves_explicit_instructions(self):
        instruction = "Keep the subject standing and preserve every explicit detail."
        report = evaluate_vision_lab_rules({"instructions": instruction})
        self.assertEqual(report.protected_instructions, instruction)
        self.assertEqual(report.draft.instructions, instruction)

    def test_does_not_mutate_input_selections(self):
        selections = {"camera_photography": {"framing": "full-body"}}
        original = {"camera_photography": {"framing": "full-body"}}
        evaluate_vision_lab_rules({"selections": selections})
        self.assertEqual(selections, original)

    def test_rejects_image_references(self):
        with self.assertRaisesRegex(ValueError, "text-only"):
            evaluate_vision_lab_rules({"references": [{"role": "look"}]})


    def test_saree_and_walking_pose_produce_non_blocking_guidance(self):
        payload = {"selections": {
            "outfit_styling": {"choices": {"garment_type": "Sambalpuri saree"}},
            "poses_expressions": {"choices": {"pose": "Walking"}},
        }}
        report = evaluate_vision_lab_rules(payload)
        guidance = [item for item in report.findings if item.code == "OUTFIT_POSE_GUIDANCE"]
        self.assertEqual(len(guidance), 1)
        self.assertEqual(guidance[0].severity, "info")
        self.assertIn("pallu direction", guidance[0].message)
        self.assertFalse(report.has_conflicts)
        self.assertEqual(
            report.draft.selections["outfit_styling"]["choices"]["garment_type"],
            "Sambalpuri saree",
        )
        self.assertEqual(
            report.draft.selections["poses_expressions"]["choices"]["pose"],
            "Walking",
        )

    def test_saree_and_seated_pose_suggest_drape_placement(self):
        report = evaluate_vision_lab_rules({"selections": {
            "outfit_styling": {"choices": {"garment_type": "Silk saree"}},
            "poses_expressions": {"choices": {"pose": "Sitting"}},
        }})
        guidance = [item for item in report.findings if item.code == "OUTFIT_POSE_GUIDANCE"]
        self.assertEqual(len(guidance), 1)
        self.assertIn("pleat placement", guidance[0].message)
        self.assertEqual(guidance[0].severity, "info")

    def test_lehenga_dynamic_pose_suggests_skirt_movement(self):
        report = evaluate_vision_lab_rules({"selections": {
            "outfit_styling": {"choices": {"garment_type": "Lehenga"}},
            "poses_expressions": {"choices": {"pose": "Dynamic movement"}},
        }})
        guidance = [item for item in report.findings if item.code == "OUTFIT_POSE_GUIDANCE"]
        self.assertEqual(len(guidance), 1)
        self.assertIn("skirt flare", guidance[0].message)
        self.assertEqual(guidance[0].severity, "info")

    def test_heel_movement_guidance_does_not_change_user_selection(self):
        report = evaluate_vision_lab_rules({"selections": {
            "outfit_styling": {"choices": {"footwear": "Heels"}},
            "poses_expressions": {"choices": {"pose": "Walking"}},
        }})
        guidance = [item for item in report.findings if item.code == "OUTFIT_POSE_GUIDANCE"]
        self.assertEqual(len(guidance), 1)
        self.assertIn("stable foot placement", guidance[0].message)
        self.assertEqual(
            report.draft.selections["outfit_styling"]["choices"]["footwear"],
            "Heels",
        )

    def test_ordinary_pose_does_not_trigger_outfit_pose_guidance(self):
        report = evaluate_vision_lab_rules({"selections": {
            "outfit_styling": {"choices": {"garment_type": "Western dress"}},
            "poses_expressions": {"choices": {"pose": "Standing"}},
        }})
        self.assertNotIn("OUTFIT_POSE_GUIDANCE", [item.code for item in report.findings])


    def test_reports_subject_count_conflict(self):
        report = evaluate_vision_lab_rules({"selections": {
            "appearance_identity": {"subject_count": "single person"},
            "poses_expressions": {"subject_count": "two people"},
        }})
        self.assertIn("SUBJECT_COUNT_CONFLICT", [item.code for item in report.findings])


if __name__ == "__main__":
    unittest.main()
