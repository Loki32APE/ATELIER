"""Validation tests for the text-only Vision Lab synthesis route."""

import unittest
from unittest.mock import patch

import app as atelier_app


class ScratchSynthesisRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = atelier_app.app.test_client()
        self.api_key = atelier_app.OPENROUTER_API_KEY
        atelier_app.OPENROUTER_API_KEY = "test-key"

    def tearDown(self):
        atelier_app.OPENROUTER_API_KEY = self.api_key

    def post(self, payload):
        return self.client.post("/synthesize-scratch", json=payload)

    def assert_rejected_without_job(self, payload, expected_error):
        with patch.object(atelier_app, "new_job") as new_job, patch.object(
            atelier_app, "WorkerThread"
        ) as thread:
            response = self.post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn(expected_error, response.get_json()["error"])
        new_job.assert_not_called()
        thread.assert_not_called()

    def test_valid_text_only_request_starts_job_with_clean_attributes(self):
        with patch.object(atelier_app, "new_job", return_value="scratch-job") as new_job, patch.object(atelier_app, "job_access_token", return_value="test-token"), patch.object(
            atelier_app, "WorkerThread"
        ) as thread:
            response = self.post({
                "raw_keywords": "cinematic editorial portrait",
                "attributes": {"hair": "Long waves", "unused": "Any"},
                "style": "editorial",
                "ar": "9:16",
                "detail": "detailed",
            })
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json(), {"job_id": "scratch-job", "access_token": "test-token"})
        new_job.assert_called_once_with("scratch", "detailed")
        args = thread.call_args.kwargs["args"]
        self.assertEqual(args, ("scratch-job", "cinematic editorial portrait",
                                {"hair": "Long waves"}, "editorial", "9:16", "detailed"))

    def test_attributes_only_request_is_allowed(self):
        with patch.object(atelier_app, "new_job", return_value="scratch-job"), patch.object(
            atelier_app, "WorkerThread"
        ):
            response = self.post({"attributes": {"hair": "Long waves"}})
        self.assertEqual(response.status_code, 202)

    def test_non_object_json_is_rejected(self):
        response = self.client.post("/synthesize-scratch", data='["bad"]',
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("JSON object", response.get_json()["error"])

    def test_image_reference_fields_are_rejected(self):
        self.assert_rejected_without_job(
            {"raw_keywords": "portrait", "references": [{"role": "look"}]},
            "Unsupported field(s): references",
        )
        self.assert_rejected_without_job(
            {"raw_keywords": "portrait", "image": "data:image/png;base64,..."},
            "Unsupported field(s): image",
        )

    def test_attributes_must_be_object(self):
        self.assert_rejected_without_job(
            {"raw_keywords": "portrait", "attributes": ["hair"]},
            "Attributes must be a JSON object",
        )

    def test_attribute_values_must_be_text(self):
        self.assert_rejected_without_job(
            {"raw_keywords": "portrait", "attributes": {"hair": ["waves"]}},
            "must have a text value",
        )

    def test_raw_keywords_over_limit_are_rejected_not_truncated(self):
        self.assert_rejected_without_job(
            {"raw_keywords": "x" * (atelier_app.MAX_TEXT_CHARS + 1)},
            "characters or fewer",
        )

    def test_oversized_attribute_value_is_rejected(self):
        self.assert_rejected_without_job(
            {"attributes": {"hair": "x" * (atelier_app.SCRATCH_MAX_ATTRIBUTE_VALUE_CHARS + 1)}},
            "must be 300 characters or fewer",
        )

    def test_invalid_detail_is_rejected(self):
        self.assert_rejected_without_job(
            {"raw_keywords": "portrait", "detail": "ultra"},
            "Detail must be fast, balanced, or detailed",
        )

    def test_invalid_aspect_ratio_is_rejected(self):
        self.assert_rejected_without_job(
            {"raw_keywords": "portrait", "ar": "wide-screen"},
            "Aspect ratio must use a format",
        )

    def test_empty_request_is_rejected(self):
        self.assert_rejected_without_job({}, "Raw keywords ya attributes")

if __name__ == "__main__":
    unittest.main()
