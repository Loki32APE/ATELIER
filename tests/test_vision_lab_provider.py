import unittest
from unittest.mock import patch

from atelier_engine.vision_lab_provider import ProviderError, chat_completion


class FakeResponse:
    def __init__(self, data=None, status=200):
        self.data = data or {"choices": [{"message": {"content": "A cinematic portrait."}}], "model": "test/model"}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            error = requests.HTTPError("failure")
            error.response = self
            raise error

    def json(self):
        return self.data


class ProviderTests(unittest.TestCase):
    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key", "VISION_LAB_MODEL": "test/model"})
    @patch("atelier_engine.vision_lab_provider.requests.post")
    def test_returns_normalized_completion(self, post):
        post.return_value = FakeResponse()
        result = chat_completion([{"role": "user", "content": "hello"}])
        self.assertEqual(result["content"], "A cinematic portrait.")
        self.assertEqual(result["model"], "test/model")

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_key_fails_safely(self):
        with self.assertRaisesRegex(ProviderError, "not configured"):
            chat_completion([{"role": "user", "content": "hello"}])

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key", "VISION_LAB_MODEL": "test/model"})
    @patch("atelier_engine.vision_lab_provider.requests.post")
    def test_auth_failure_does_not_expose_response_body(self, post):
        post.return_value = FakeResponse(status=401)
        with self.assertRaisesRegex(ProviderError, "authentication failed"):
            chat_completion([{"role": "user", "content": "hello"}])


if __name__ == "__main__":
    unittest.main()
