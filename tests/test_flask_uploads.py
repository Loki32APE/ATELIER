"""Tests for the isolated legacy Studio upload integration boundary."""

import io
import unittest
from io import BytesIO

from PIL import Image

from atelier_engine.flask_uploads import prepare_legacy_studio_request


class FakeFileStorage:
    def __init__(self, filename, mimetype, content):
        self.filename = filename
        self.mimetype = mimetype
        self.stream = io.BytesIO(content)


def make_png():
    buffer = BytesIO()
    Image.new("RGB", (1, 1), "white").save(buffer, format="PNG")
    return buffer.getvalue()


PNG = make_png()


class TrackingStream(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.requested_size = None

    def read(self, size=-1):
        self.requested_size = size
        return super().read(size)


class FlaskUploadIntegrationTests(unittest.TestCase):
    def test_prepares_look_and_outfit_payload_and_preserves_bytes(self):
        result = prepare_legacy_studio_request(
            {"output": "full", "detail": "detailed"},
            {
                "image1": FakeFileStorage("look.png", "image/png", PNG),
                "image2": FakeFileStorage("outfit.png", "image/png", PNG),
            },
        )
        self.assertEqual(
            [item["role"] for item in result.payload["references"]],
            ["look", "outfit"],
        )
        self.assertEqual(result.uploads_by_field["image1"].content, PNG)
        self.assertEqual(result.payload["options"]["detail"], "detailed")

    def test_rejects_mime_signature_mismatch(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            prepare_legacy_studio_request(
                {"output": "full"},
                {"image1": FakeFileStorage("look.png", "image/png", b"not an image")},
            )

    def test_rejects_unsafe_filename(self):
        with self.assertRaisesRegex(ValueError, "unsafe filename"):
            prepare_legacy_studio_request(
                {"output": "full"},
                {"image1": FakeFileStorage("../look.png", "image/png", PNG)},
            )

    def test_rejects_unsupported_image_type(self):
        with self.assertRaisesRegex(ValueError, "unsupported image type"):
            prepare_legacy_studio_request(
                {"output": "full"},
                {"image1": FakeFileStorage("look.gif", "image/gif", b"GIF89a")},
            )

    def test_rejects_oversized_image(self):
        content = PNG + b"x" * (4 * 1024 * 1024)
        with self.assertRaisesRegex(ValueError, "per-image size limit"):
            prepare_legacy_studio_request(
                {"output": "full"},
                {"image1": FakeFileStorage("large.png", "image/png", content)},
            )

    def test_oversized_upload_is_read_only_to_limit_plus_one_byte(self):
        from atelier_engine.uploads import MAX_REFERENCE_BYTES

        file_obj = FakeFileStorage(
            "large.png", "image/png", PNG + b"x" * (MAX_REFERENCE_BYTES + 100)
        )
        tracking_stream = TrackingStream(file_obj.stream.getvalue())
        file_obj.stream = tracking_stream

        with self.assertRaisesRegex(ValueError, "per-image size limit"):
            prepare_legacy_studio_request(
                {"output": "full"}, {"image1": file_obj}
            )

        self.assertEqual(tracking_stream.requested_size, MAX_REFERENCE_BYTES + 1)
        self.assertEqual(tracking_stream.tell(), 0)

    def test_empty_browser_filename_is_treated_as_missing(self):
        with self.assertRaisesRegex(ValueError, "At least one Look or Outfit"):
            prepare_legacy_studio_request(
                {"output": "full"},
                {"image1": FakeFileStorage("", "image/png", PNG)},
            )

    def test_upload_stream_is_restored_after_reading(self):
        file_obj = FakeFileStorage("look.png", "image/png", PNG)
        prepare_legacy_studio_request(
            {"output": "full"}, {"image1": file_obj}
        )
        self.assertEqual(file_obj.stream.tell(), 0)

    def test_raw_payload_keeps_look_metadata_but_preserves_validated_outfit_bytes(self):
        result = prepare_legacy_studio_request(
            {"output": "raw"},
            {
                "image1": FakeFileStorage("look.png", "image/png", PNG),
                "image2": FakeFileStorage("outfit.png", "image/png", PNG),
            },
        )
        self.assertEqual([r["role"] for r in result.payload["references"]], ["look"])
        self.assertIn("image2", result.uploads_by_field)

    def test_rejects_non_mapping_files(self):
        with self.assertRaisesRegex(ValueError, "files must be a mapping"):
            prepare_legacy_studio_request({"output": "full"}, None)


if __name__ == "__main__":
    unittest.main()
