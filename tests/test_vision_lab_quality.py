import unittest

from atelier_engine.vision_lab_quality import validate_prompt_quality


class VisionLabQualityTests(unittest.TestCase):
    def test_passes_valid_prompt_with_protected_instruction(self):
        prompt = "A cinematic portrait with natural light. Keep the blue coat unchanged."
        report = validate_prompt_quality(prompt, protected_instructions="Keep the blue coat unchanged.")
        self.assertTrue(report.passed)
        self.assertEqual(report.score, 100)

    def test_fails_when_protected_instruction_is_missing(self):
        report = validate_prompt_quality("A detailed cinematic portrait with natural light.", protected_instructions="Keep the blue coat.")
        self.assertFalse(report.passed)
        self.assertIn("INSTRUCTION_LOSS", [x.code for x in report.issues])

    def test_reports_empty_and_overlong_prompt(self):
        empty = validate_prompt_quality("")
        self.assertFalse(empty.passed)
        long = validate_prompt_quality("word " * 30, max_chars=20)
        self.assertIn("PROMPT_TOO_LONG", [x.code for x in long.issues])


if __name__ == "__main__":
    unittest.main()
