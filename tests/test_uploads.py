"""Tests for safe reference upload validation."""

import unittest
from unittest.mock import patch
from io import BytesIO

from PIL import Image

from atelier_engine.uploads import (
    MAX_REFERENCE_BYTES,
    ReferenceUpload,
    validate_reference_uploads,
)


def make_png(width=1, height=1):
    buffer = BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


PNG = make_png()


class ReferenceUploadTests(unittest.TestCase):
    def test_accepts_valid_png_signature(self):
        upload = ReferenceUpload(
            "reference.png",
            "image/png",
            PNG,
        )
        self.assertTrue(validate_reference_uploads([upload]).valid)

    def test_rejects_signature_only_fake_png(self):
        upload = ReferenceUpload("fake.png", "image/png", b"\x89PNG\r\n\x1a\n" + b"not-a-real-png")
        result = validate_reference_uploads([upload])
        self.assertFalse(result.valid)
        self.assertTrue(any("safely decodable" in error for error in result.errors))

    def test_rejects_mime_signature_mismatch(self):
        upload = ReferenceUpload(
            "reference.png",
            "image/png",
            b"\xff\xd8\xff" + b"not-a-png",
        )
        result = validate_reference_uploads([upload])
        self.assertFalse(result.valid)
        self.assertTrue(any("does not match" in error for error in result.errors))

    def test_rejects_unsafe_filename(self):
        upload = ReferenceUpload(
            "../secret.png",
            "image/png",
            PNG,
        )
        self.assertFalse(validate_reference_uploads([upload]).valid)

    def test_rejects_oversized_image(self):
        upload = ReferenceUpload(
            "large.png",
            "image/png",
            b"\x89PNG\r\n\x1a\n" + b"x" * MAX_REFERENCE_BYTES,
        )
        result = validate_reference_uploads([upload])
        self.assertFalse(result.valid)
        self.assertTrue(any("per-image size limit" in error for error in result.errors))

    def test_rejects_images_over_pixel_limit(self):
        upload = ReferenceUpload("large-dimensions.png", "image/png", PNG)
        with patch("atelier_engine.uploads.MAX_IMAGE_PIXELS", 0):
            result = validate_reference_uploads([upload])
        self.assertFalse(result.valid)
        self.assertTrue(any("pixel limit" in error for error in result.errors))

    def test_rejects_too_many_references(self):
        upload = ReferenceUpload(
            "reference.png",
            "image/png",
            b"\x89PNG\r\n\x1a\n" + b"test",
        )
        result = validate_reference_uploads([upload] * 7)
        self.assertFalse(result.valid)
        self.assertTrue(any("No more than" in error for error in result.errors))

    def test_rejects_empty_upload_collection(self):
        result = validate_reference_uploads([])
        self.assertFalse(result.valid)
        self.assertIn("At least one reference image is required.", result.errors)


if __name__ == "__main__":
    unittest.main()
