"""Provider failures are isolated per reference-analysis task."""
import unittest
from unittest.mock import patch

import app as atelier_app


class StudioProviderAnalysisTests(unittest.TestCase):
    def test_outfit_failure_does_not_discard_successful_look_analysis(self):
        def fake_describe(img, mime, prompt, label, max_tokens):
            if label == "outfit":
                raise atelier_app.LLMError("provider unavailable")
            return "Look framing, pose and lighting."

        with patch.object(atelier_app, "describe_image", side_effect=fake_describe):
            look, outfit, errors = atelier_app.analyze_look_and_outfit(
                (b"look", "image/jpeg"), (b"outfit", "image/jpeg"),
                "", atelier_app.DETAIL_LEVELS["fast"]
            )
        self.assertIn("Look framing", look)
        self.assertEqual(outfit, "")
        self.assertIn("outfit", errors)

    def test_split_look_keeps_successful_half_when_other_half_fails(self):
        def fake_describe(img, mime, prompt, label, max_tokens):
            if label == "look-detail":
                raise atelier_app.LLMError("provider unavailable")
            return "Look pose and framing."

        with patch.object(atelier_app, "describe_image", side_effect=fake_describe):
            look, outfit, errors = atelier_app.analyze_look_and_outfit(
                (b"look", "image/jpeg"), None, "",
                atelier_app.DETAIL_LEVELS["balanced"]
            )
        self.assertIn("Look pose", look)
        self.assertEqual(outfit, "")
        self.assertIn("look_detail", errors)


if __name__ == "__main__":
    unittest.main()
