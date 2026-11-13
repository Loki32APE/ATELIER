import unittest

from atelier_engine.model_profiles import get_model_profile, list_model_profiles


class ModelProfileTests(unittest.TestCase):
    def test_known_profile_is_resolved(self):
        profile = get_model_profile("black-forest-labs/flux.1-pro")
        self.assertEqual(profile.preferred_format, "concise_natural_language")

    def test_unknown_model_uses_neutral_profile(self):
        profile = get_model_profile("vendor/not-listed")
        self.assertEqual(profile.model_id, "unknown")
        self.assertEqual(profile.preferred_format, "natural_language")

    def test_profile_list_is_serializable(self):
        self.assertTrue(list_model_profiles())


if __name__ == "__main__":
    unittest.main()
