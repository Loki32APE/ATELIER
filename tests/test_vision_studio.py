import unittest

from prompts import LOOK_FAST_PROMPT, LOOK_PART_A_PROMPT, LOOK_PART_B_PROMPT, OUTFIT_PROMPT

from atelier_engine.vision_studio import (
    build_studio_intelligence, build_studio_prompt_context, build_studio_analysis_report,
    validate_reference_analysis, validate_studio_prompt,
)


class VisionStudioIntelligenceTests(unittest.TestCase):
    def _payload(self, output="full", look=True, outfit=True):
        refs = []
        if look:
            refs.append({"reference_id": "legacy-look", "role": "look", "mime_type": "image/jpeg"})
        if outfit:
            refs.append({"reference_id": "legacy-outfit", "role": "outfit", "mime_type": "image/png"})
        return {"workspace": "vision_studio", "instructions": "", "references": refs,
                "options": {"detail": "balanced", "output": output}}

    def test_look_and_outfit_have_distinct_analysis_scopes(self):
        result = build_studio_intelligence(self._payload(), {})
        scopes = {item["role"]: item for item in result["reference_manifest"]}
        self.assertIn("pose, action and gaze", scopes["look"]["analysis_scope"])
        self.assertIn("fabric physics", " ".join(scopes["outfit"]["analysis_scope"]))
        self.assertIn("hairstyle and hair length", scopes["look"]["excluded_scope"])
        self.assertIn("background", scopes["outfit"]["excluded_scope"])

    def test_explicit_directives_are_marked_as_overrides(self):
        result = build_studio_intelligence(
            self._payload(), {"subject_text": "Natural proportions", "hair_text": "Long braid"}
        )
        self.assertEqual(result["creative_directives"]["subject_physique"]["priority"], "explicit_user_override")
        self.assertEqual(result["creative_directives"]["hairstyle"]["value"], "Long braid")

    def test_outfit_override_reports_reference_conflict(self):
        result = build_studio_intelligence(self._payload(), {"outfit_override": "Ivory silk saree"})
        self.assertTrue(any("takes priority" in item for item in result["warnings"]))

    def test_priority_policy_places_user_override_above_references_and_ai(self):
        result = build_studio_intelligence(self._payload(), {"outfit_override": "Ivory silk saree"})
        self.assertEqual(result["priority_policy"]["ordered_sources"][0], "explicit_user_directives")
        self.assertTrue(result["priority_policy"]["ai_suggestions_are_non_authoritative"])
        self.assertIn("never blend incompatible garment identities", build_studio_prompt_context(result).lower())

    def test_analysis_report_explains_outfit_override_resolution(self):
        intelligence = build_studio_intelligence(self._payload(), {"outfit_override": "Ivory silk saree"})
        report = build_studio_analysis_report(intelligence, "Look pose and warm lighting.", "Blue cotton kurta with embroidery.")
        item = report["conflict_resolution"][0]
        self.assertEqual(item["winner"], "outfit_text_override")
        self.assertEqual(item["status"], "resolved")

    def test_analysis_report_explains_look_and_outfit_reference_scope_priority(self):
        intelligence = build_studio_intelligence(self._payload(), {})
        report = build_studio_analysis_report(intelligence, "Person in a red dress, side pose.", "Blue silk saree.")
        item = report["conflict_resolution"][0]
        self.assertEqual(item["winner"], "outfit_reference_for_garments")
        self.assertEqual(item["status"], "policy_applied")

    def test_additional_instructions_outrank_ai_suggestions(self):
        intelligence = build_studio_intelligence(self._payload(), {"additional_instructions": "Keep the scene natural"})
        report = build_studio_analysis_report(intelligence, "Look description", "Outfit description")
        self.assertEqual(report["conflict_resolution"][-1]["winner"], "additional_instructions")

    def test_look_pose_analysis_requires_all_requested_sections(self):
        text = 'FRAMING: medium.\nVISIBLE RANGE: head to waist.\nPOSE AND ACTION: seated.\nAND GAZE: looking at camera.\nFOOTWEAR: none.\nAVOID: blur.'
        result = validate_reference_analysis('look_pose', text)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['coverage_score'], 100)

    def test_outfit_analysis_marks_missing_fabric_physics_as_partial(self):
        text = 'GARMENTS: blue cotton saree.\nFOOTWEAR: none.\nJEWELLERY AND ACCESSORIES: gold earrings.\nLIPSTICK: none.\nMEHNDI: none.\nAVOID: distortion.'
        result = validate_reference_analysis('outfit', text)
        self.assertEqual(result['status'], 'partial')
        self.assertIn('FABRIC PHYSICS', result['missing_sections'])
        self.assertTrue(result['review_required'])

    def test_empty_reference_analysis_is_failed(self):
        result = validate_reference_analysis('look_detail', '')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['coverage_score'], 0)
    def test_analysis_prompt_labels_match_validator_contract(self):
        cases = {
            'look': (LOOK_FAST_PROMPT, ('FRAMING', 'VISIBLE RANGE', 'POSE AND ACTION', 'AND GAZE', 'FOOTWEAR', 'LIGHTING AND CAMERA', 'BACKGROUND AND ENVIRONMENT', 'MAKEUP', 'GARMENTS', 'JEWELLERY AND ACCESSORIES', 'AVOID')),
            'look_pose': (LOOK_PART_A_PROMPT, ('FRAMING', 'VISIBLE RANGE', 'POSE AND ACTION', 'AND GAZE', 'FOOTWEAR', 'AVOID')),
            'look_detail': (LOOK_PART_B_PROMPT, ('LIGHTING AND CAMERA', 'BACKGROUND AND ENVIRONMENT', 'MAKEUP', 'GARMENTS', 'JEWELLERY AND ACCESSORIES', 'AVOID')),
            'outfit': (OUTFIT_PROMPT, ('GARMENTS', 'FABRIC PHYSICS', 'FOOTWEAR', 'JEWELLERY AND ACCESSORIES', 'LIPSTICK', 'MEHNDI', 'AVOID')),
        }
        for task, (prompt, labels) in cases.items():
            with self.subTest(task=task):
                self.assertEqual(tuple(label for label in labels if label + ':' in prompt), labels)
                self.assertEqual(validate_reference_analysis(task, '\n'.join(label + ': evidence' for label in labels))['status'], 'ready')

    def test_duplicate_analysis_sections_require_review(self):
        labels = ('FRAMING', 'VISIBLE RANGE', 'POSE AND ACTION', 'AND GAZE', 'FOOTWEAR', 'AVOID')
        text = '\n'.join(label + ': evidence' for label in labels) + '\nFRAMING: second value'
        result = validate_reference_analysis('look_pose', text)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['duplicate_sections'], ['FRAMING'])
        self.assertEqual(result['coverage_score'], 100)

    def test_empty_first_duplicate_does_not_hide_later_evidence(self):
        labels = ('FRAMING', 'VISIBLE RANGE', 'POSE AND ACTION', 'AND GAZE', 'FOOTWEAR', 'AVOID')
        text = 'FRAMING: \n' + '\n'.join(label + ': evidence' for label in labels)
        result = validate_reference_analysis('look_pose', text)
        self.assertIn('FRAMING', result['present_sections'])
        self.assertEqual(result['status'], 'partial')
    def test_raw_mode_excludes_outfit_reference(self):
        result = build_studio_intelligence(self._payload("raw"), {})
        self.assertEqual([x["role"] for x in result["reference_manifest"]], ["look"])
        self.assertTrue(any("Look analysis only" in item for item in result["warnings"]))

    def test_raw_mode_requires_look_reference(self):
        with self.assertRaisesRegex(ValueError, "Look reference"):
            build_studio_intelligence(self._payload("raw", look=False, outfit=True), {})

    def test_manifest_does_not_claim_visual_analysis_is_complete(self):
        result = build_studio_intelligence(self._payload(), {})
        self.assertEqual(result["visual_analysis_status"], "pending_provider_analysis")

    def test_identity_framing_and_fabric_guards_are_explicit(self):
        result = build_studio_intelligence(self._payload(), {})
        self.assertTrue(result["identity_preservation"]["enabled"])
        self.assertTrue(result["smart_framing"]["enabled"])
        self.assertTrue(result["fabric_physics"]["enabled"])
        context = build_studio_prompt_context(result)
        self.assertIn("Never copy facial identity", context)
        self.assertIn("Smart framing", context)
        self.assertIn("Fabric physics", context)

    def test_additional_instruction_is_an_explicit_override(self):
        result = build_studio_intelligence(
            self._payload(), {"additional_instructions": "Keep the scene natural."}
        )
        self.assertEqual(result["creative_directives"]["additional_instructions"]["value"],
                         "Keep the scene natural.")

    def test_directive_length_is_rejected_not_silently_truncated(self):
        with self.assertRaisesRegex(ValueError, "exceeds"):
            build_studio_intelligence(self._payload(), {"hair_text": "x" * 1501})


    def test_reference_analysis_report_scores_coverage_and_lists_conflicts(self):
        intelligence = build_studio_intelligence(
            self._payload(), {"outfit_override": "Black silk dress"}
        )
        report = build_studio_analysis_report(
            intelligence, "Look framing, pose and warm light.", "Blue cotton saree with woven border."
        )
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["coverage_score"], 100)
        self.assertIn("takes priority", report["conflicts"][0])
        self.assertIn("does not measure image accuracy", report["score_note"])

    def test_reference_analysis_report_marks_missing_provider_result_partial(self):
        intelligence = build_studio_intelligence(self._payload(), {})
        report = build_studio_analysis_report(intelligence, "Pose and framing.")
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["references"]["outfit"]["status"], "failed")
        self.assertTrue(report["review_required"])

    def test_raw_report_marks_outfit_as_excluded_not_missing(self):
        intelligence = build_studio_intelligence(self._payload("raw"), {})
        report = build_studio_analysis_report(intelligence, "Look framing and pose.")
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["references"]["look"]["status"], "ready")
        self.assertEqual(report["references"]["outfit"]["status"], "excluded")

    def test_full_report_marks_selected_but_unanalyzed_outfit_as_failed(self):
        intelligence = build_studio_intelligence(self._payload(), {})
        report = build_studio_analysis_report(intelligence, "Look framing and pose.")
        self.assertEqual(report["references"]["outfit"]["status"], "failed")


    def test_single_selected_reference_receives_full_coverage_score(self):
        intelligence = build_studio_intelligence(self._payload(look=True, outfit=False), {})
        report = build_studio_analysis_report(intelligence, "Look framing and pose.")
        self.assertEqual(report["coverage_score"], 100)
        self.assertEqual(report["status"], "ready")

    def test_partial_provider_failure_is_visible_in_reference_status(self):
        intelligence = build_studio_intelligence(self._payload(), {})
        report = build_studio_analysis_report(
            intelligence, "Look framing and pose.", "Outfit fabric and construction.",
            {"look_detail": "Look detail analysis could not be completed. Retry this reference."}
        )
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["references"]["look"]["status"], "partial")
        self.assertEqual(report["references"]["outfit"]["status"], "ready")
        self.assertEqual(report["coverage_score"], 50)
        self.assertTrue(report["review_required"])

    def test_prompt_validation_does_not_rewrite_user_content(self):
        prompt = "SUBJECT PHYSIQUE: Preserve the reference subject.\nHAIRSTYLE: Long braid."
        result = validate_studio_prompt(
            prompt, build_studio_intelligence(self._payload(look=True, outfit=False), {"hair_text": "Long braid"})
        )
        self.assertTrue(result["passed"])
        self.assertFalse(result["rewritten"])

    def test_prompt_validator_checks_directive_content_not_only_section_presence(self):
        intelligence = build_studio_intelligence(
            self._payload(look=True, outfit=False), {"hair_text": "Long center-parted braid with soft natural waves"}
        )
        report = validate_studio_prompt("HAIRSTYLE: Short pixie haircut.", intelligence)
        self.assertFalse(report["passed"])
        self.assertEqual(report["instruction_integrity"], "review_required")
        self.assertTrue(any("hairstyle directive" in item.lower() for item in report["warnings"]))
        self.assertTrue(report["suggestions"])

    def test_prompt_validator_accepts_matching_explicit_directives(self):
        intelligence = build_studio_intelligence(
            self._payload(look=True, outfit=False), {"hair_text": "Long center-parted braid with soft natural waves"}
        )
        report = validate_studio_prompt(
            "HAIRSTYLE: Long center-parted braid with soft natural waves.", intelligence
        )
        self.assertTrue(report["passed"])
        self.assertEqual(report["instruction_integrity"], "preserved")

    def test_prompt_validator_flags_duplicate_sections(self):
        intelligence = build_studio_intelligence(self._payload(), {})
        report = validate_studio_prompt(
            "SUBJECT PHYSIQUE: Natural proportions.\nSUBJECT PHYSIQUE: Realistic body.",
            intelligence,
        )
        self.assertFalse(report["passed"])
        self.assertTrue(any("Duplicate prompt sections" in item for item in report["warnings"]))

    def test_master_prompt_warns_when_selected_outfit_has_no_outfit_section(self):
        intelligence = build_studio_intelligence(self._payload(), {})
        report = validate_studio_prompt("SUBJECT PHYSIQUE: Natural proportions.", intelligence)
        self.assertFalse(report["passed"])
        self.assertTrue(any("no OUTFIT section" in item for item in report["warnings"]))

    def test_additional_instruction_is_checked_against_final_prompt(self):
        intelligence = build_studio_intelligence(
            self._payload(), {"additional_instructions": "Keep the scene warm and cinematic"}
        )
        report = validate_studio_prompt("QUALITY: sharp photorealistic details.", intelligence)
        self.assertEqual(report["instruction_integrity"], "review_required")

    def test_raw_prompt_validation_flags_missing_fixed_outfit_line(self):
        intelligence = build_studio_intelligence(self._payload("raw"), {})
        result = validate_studio_prompt("SUBJECT PHYSIQUE: Keep identity.", intelligence)
        self.assertFalse(result["passed"])
        self.assertTrue(any("fixed system line" in item for item in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
