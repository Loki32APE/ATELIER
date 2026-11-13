"""Tests for adapting the legacy Studio form into the shared contract."""

import unittest

from atelier_engine.adapters import adapt_legacy_studio_request


class LegacyStudioAdapterTests(unittest.TestCase):
    def test_maps_existing_look_and_outfit_fields(self):
        payload = adapt_legacy_studio_request(
            {
                "output": "full",
                "detail": "detailed",
                "subject_text": "Keep natural proportions",
                "hair_text": "Loose braid",
                "pose_text": "Standing",
                "outfit_override": "Blue dress",
            },
            {
                "image1": {"mime_type": "image/jpeg", "filename": "look.jpg"},
                "image2": {"mime_type": "image/png", "filename": "outfit.png"},
            },
        )
        self.assertEqual(payload["workspace"], "vision_studio")
        self.assertEqual([r["role"] for r in payload["references"]], ["look", "outfit"])
        self.assertIn("Subject / physique: Keep natural proportions", payload["instructions"])
        self.assertEqual(payload["options"], {"detail": "detailed", "output": "full"})

    def test_maps_look_only_full_request(self):
        payload = adapt_legacy_studio_request(
            {"output": "full"}, {"image1": {"mime_type": "image/webp"}}
        )
        self.assertEqual([r["role"] for r in payload["references"]], ["look"])

    def test_maps_outfit_only_full_request(self):
        payload = adapt_legacy_studio_request(
            {"output": "full"}, {"image2": {"mime_type": "image/jpeg"}}
        )
        self.assertEqual([r["role"] for r in payload["references"]], ["outfit"])

    def test_raw_requires_look_and_drops_outfit(self):
        payload = adapt_legacy_studio_request(
            {"output": "raw"},
            {
                "image1": {"mime_type": "image/jpeg"},
                "image2": {"mime_type": "image/png"},
            },
        )
        self.assertEqual([r["role"] for r in payload["references"]], ["look"])

    def test_raw_without_look_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "RAW output requires a Look"):
            adapt_legacy_studio_request(
                {"output": "raw"}, {"image2": {"mime_type": "image/png"}}
            )

    def test_full_without_references_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "At least one Look or Outfit"):
            adapt_legacy_studio_request({"output": "full"}, {})

    def test_invalid_mime_is_rejected_by_shared_validator(self):
        with self.assertRaisesRegex(ValueError, "unsupported image MIME"):
            adapt_legacy_studio_request(
                {"output": "full"}, {"image1": {"mime_type": "image/gif"}}
            )

    def test_invalid_output_falls_back_to_full_like_legacy_route(self):
        payload = adapt_legacy_studio_request(
            {"output": "unknown"}, {"image1": {"mime_type": "image/jpeg"}}
        )
        self.assertEqual(payload["options"]["output"], "full")

    def test_invalid_detail_falls_back_to_balanced(self):
        payload = adapt_legacy_studio_request(
            {"output": "full", "detail": "turbo"},
            {"image1": {"mime_type": "image/jpeg"}},
        )
        self.assertEqual(payload["options"]["detail"], "balanced")

    def test_truncates_legacy_directives_to_route_limit(self):
        payload = adapt_legacy_studio_request(
            {"output": "full", "subject_text": "x" * 1600},
            {"image1": {"mime_type": "image/jpeg"}},
        )
        value = payload["instructions"].split(": ", 1)[1]
        self.assertEqual(len(value), 1500)

    def test_non_text_directive_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "subject_text must be text"):
            adapt_legacy_studio_request(
                {"output": "full", "subject_text": ["bad"]},
                {"image1": {"mime_type": "image/jpeg"}},
            )


if __name__ == "__main__":
    unittest.main()
