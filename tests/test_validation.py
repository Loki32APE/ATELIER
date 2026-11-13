"""Tests for Atelier's provider-neutral workspace request validation."""

import unittest

from atelier_engine.validation import (
    normalize_workspace_request,
    validate_workspace_request,
)


class WorkspaceValidationTests(unittest.TestCase):
    def test_valid_vision_lab_request(self):
        result = validate_workspace_request(
            {"workspace": "vision_lab", "instructions": "A cinematic portrait"}
        )
        self.assertTrue(result.valid)

    def test_vision_lab_rejects_references_during_normalization(self):
        payload = {
            "workspace": "vision_lab",
            "instructions": "A cinematic portrait",
            "references": [{
                "reference_id": "ref-1",
                "role": "inspiration",
                "mime_type": "image/jpeg",
            }],
        }
        with self.assertRaisesRegex(ValueError, "Vision Lab is text-only"):
            normalize_workspace_request(payload)

    def test_vision_studio_requires_reference(self):
        result = validate_workspace_request({"workspace": "vision_studio"})
        self.assertFalse(result.valid)
        self.assertIn("Vision Studio requires at least one reference image.", result.errors)

    def test_rejects_unsupported_image_type(self):
        result = validate_workspace_request({
            "workspace": "vision_studio",
            "references": [{
                "reference_id": "look-1",
                "role": "look",
                "mime_type": "image/gif",
            }],
        })
        self.assertFalse(result.valid)
        self.assertTrue(any("unsupported image MIME type" in e for e in result.errors))

    def test_rejects_non_object_request(self):
        result = validate_workspace_request([])
        self.assertFalse(result.valid)
        self.assertIn("Request must be a JSON object.", result.errors)

    def test_rejects_duplicate_reference_ids(self):
        reference = {
            "reference_id": "same-id",
            "role": "look",
            "mime_type": "image/jpeg",
        }
        result = validate_workspace_request({
            "workspace": "vision_studio",
            "references": [reference, reference],
        })
        self.assertFalse(result.valid)
        self.assertTrue(any("Duplicate reference_id" in e for e in result.errors))

    def test_normalizes_valid_request(self):
        request = normalize_workspace_request({
            "workspace": "vision_studio",
            "instructions": "Preserve the overall composition.",
            "references": [{
                "reference_id": "look-1",
                "role": "look",
                "mime_type": "image/jpeg",
                "filename": "look.jpg",
            }],
            "options": {"detail": "balanced"},
        })
        self.assertEqual(request.workspace, "vision_studio")
        self.assertEqual(request.references[0].filename, "look.jpg")


if __name__ == "__main__":
    unittest.main()
