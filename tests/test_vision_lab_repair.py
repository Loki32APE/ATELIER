import unittest
from unittest.mock import patch

from atelier_engine.vision_lab_repair import propose_prompt_repair


class VisionLabRepairTests(unittest.TestCase):
    @patch("atelier_engine.vision_lab_repair.chat_completion")
    def test_returns_comparison_and_requires_user_decision(self, completion):
        completion.return_value = {
            "content": "A cinematic portrait in natural light. Preserve the blue coat.",
            "model": "mock/model",
        }
        result = propose_prompt_repair(
            "A portrait. Preserve the blue coat.",
            protected_instructions="Preserve the blue coat.",
            model_id="mock/model",
        )
        self.assertEqual(result["status"], "review_required")
        self.assertTrue(result["user_decision_required"])
        self.assertIn("original_prompt", result)
        self.assertIn("repaired_prompt", result)
        self.assertTrue(result["repaired_quality"]["passed"])


if __name__ == "__main__":
    unittest.main()
