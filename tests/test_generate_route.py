"""Integration tests for the legacy /generate upload boundary."""

import io
from io import BytesIO

from PIL import Image
import unittest
from unittest.mock import patch

import app as atelier_app


buffer = BytesIO()
Image.new("RGB", (1, 1), "white").save(buffer, format="PNG")
PNG = buffer.getvalue()


class GenerateRouteUploadTests(unittest.TestCase):
    def setUp(self):
        self.client = atelier_app.app.test_client()
        self.api_key = atelier_app.OPENROUTER_API_KEY
        atelier_app.OPENROUTER_API_KEY = "test-key"

    def tearDown(self):
        atelier_app.OPENROUTER_API_KEY = self.api_key

    def test_full_generation_receives_validated_look_and_outfit_bytes(self):
        with patch.object(atelier_app, "new_job", return_value="test-job"), patch.object(atelier_app, "job_access_token", return_value="test-token"), patch.object(
            atelier_app, "WorkerThread"
        ) as thread:
            response = self.client.post(
                "/generate",
                data={
                    "output": "full",
                    "detail": "balanced",
                    "additional_instructions": "Warm cinematic evening light.",
                    "image1": (io.BytesIO(PNG), "look.png", "image/png"),
                    "image2": (io.BytesIO(PNG), "outfit.png", "image/png"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json(), {"job_id": "test-job", "access_token": "test-token"})
        args = thread.call_args.kwargs["args"]
        self.assertEqual(args[1], (PNG, "image/png"))
        self.assertEqual(args[2], (PNG, "image/png"))
        studio_contract = args[-1]
        self.assertEqual(studio_contract["workspace"], "vision_studio")
        self.assertEqual(
            {item["role"] for item in studio_contract["reference_manifest"]},
            {"look", "outfit"},
        )
        self.assertTrue(studio_contract["identity_preservation"]["enabled"])
        self.assertEqual(studio_contract["creative_directives"]["additional_instructions"]["value"], "Warm cinematic evening light.")

    def test_raw_generation_uses_look_and_ignores_outfit_for_processing(self):
        with patch.object(atelier_app, "new_job", return_value="raw-job"), patch.object(atelier_app, "job_access_token", return_value="test-token"), patch.object(
            atelier_app, "WorkerThread"
        ) as thread:
            response = self.client.post(
                "/generate",
                data={
                    "output": "raw",
                    "image1": (io.BytesIO(PNG), "look.png", "image/png"),
                    "image2": (io.BytesIO(PNG), "outfit.png", "image/png"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 202)
        args = thread.call_args.kwargs["args"]
        self.assertEqual(args[1], (PNG, "image/png"))
        self.assertIsNone(args[2])
        self.assertEqual(
            [item["role"] for item in args[-1]["reference_manifest"]],
            ["look"],
        )

    def test_invalid_image_signature_is_rejected_before_job_creation(self):
        with patch.object(atelier_app, "new_job") as new_job:
            response = self.client.post(
                "/generate",
                data={
                    "output": "full",
                    "image1": (io.BytesIO(b"not-a-real-image"), "look.png", "image/png"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("does not match", response.get_json()["error"])
        new_job.assert_not_called()

    def test_missing_reference_is_rejected(self):
        response = self.client.post(
            "/generate",
            data={"output": "full"},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("At least one Look or Outfit reference", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
