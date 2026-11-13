"""Regression coverage for security and capacity safeguards."""

import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import app as atelier_app


def _raise_security_test_error():
    raise RuntimeError("private-internal-stack-detail")


atelier_app.app.add_url_rule(
    "/_security_test_internal_error",
    endpoint="_security_test_internal_error",
    view_func=_raise_security_test_error,
)


class SecurityHardeningTests(unittest.TestCase):
    def setUp(self):
        self.client = atelier_app.app.test_client()

    def test_browser_security_headers_are_present_on_application_responses(self):
        response = self.client.get("/")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(
            response.headers.get("Permissions-Policy"),
            "camera=(), microphone=(), geolocation=()",
        )

    def test_unhandled_server_error_returns_generic_json_without_exception_details(self):
        secret = "private-internal-stack-detail"
        response = self.client.get("/_security_test_internal_error")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.mimetype, "application/json")
        self.assertNotIn(secret, response.get_data(as_text=True))
        self.assertEqual(
            response.get_json()["error"],
            "An unexpected server error occurred. Please retry.",
        )
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

    def test_application_does_not_issue_session_cookie_or_enable_permissive_cors(self):
        response = self.client.get("/")
        self.assertIsNone(response.headers.get("Set-Cookie"))
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
    def test_unknown_job_and_unauthorized_job_have_same_response(self):
        original_jobs = atelier_app.jobs.copy()
        job_id = "b" * 32
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs[job_id] = {
                    "status": "done", "created": 1, "finished_at": 2,
                    "access_token": "private-token", "prompt": "private",
                }
            unknown = self.client.get(f"/status/{'c' * 32}")
            unauthorized = self.client.get(f"/status/{job_id}")
            self.assertEqual(unknown.status_code, unauthorized.status_code)
            self.assertEqual(unknown.get_json(), unauthorized.get_json())
            self.assertEqual(unknown.headers.get("Cache-Control"), "no-store")
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_job_status_requires_bearer_token_and_never_caches_results(self):
        original_jobs = atelier_app.jobs.copy()
        job_id = "a" * 32
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs[job_id] = {
                    "kind": "test",
                    "status": "done",
                    "created": atelier_app.time.time(),
                    "finished_at": atelier_app.time.time(),
                    "access_token": "secret-token",
                    "prompt": "private prompt",
                }

            denied = self.client.get(f"/status/{job_id}")
            self.assertEqual(denied.status_code, 404)
            self.assertEqual(denied.headers.get("Cache-Control"), "no-store")
            self.assertNotIn("private prompt", denied.get_data(as_text=True))

            allowed = self.client.get(
                f"/status/{job_id}",
                headers={"Authorization": "Bearer secret-token"},
            )
            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(allowed.headers.get("Cache-Control"), "no-store")
            self.assertEqual(allowed.get_json()["prompt"], "private prompt")
            self.assertNotIn("access_token", allowed.get_json())
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_post_api_responses_are_explicitly_non_cacheable(self):
        response = self.client.post("/vision-lab/validate", json={
            "prompt": "private creative prompt", "instructions": "", "target_model_id": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertEqual(response.headers.get("Pragma"), "no-cache")

    def test_sensitive_repair_response_is_not_cacheable(self):
        with patch.object(atelier_app, "OPENROUTER_API_KEY", "test-key"), patch.object(
            atelier_app, "propose_prompt_repair", return_value={"prompt": "repaired"}
        ):
            response = self.client.post("/vision-lab/repair", json={
                "prompt": "private original prompt", "instructions": "", "target_model_id": "",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertEqual(response.headers.get("Pragma"), "no-cache")
    def test_telegram_reply_disables_redirects_for_secret_bearing_request(self):
        with patch.object(atelier_app, "TELEGRAM_TOKEN", "test-token"), patch.object(atelier_app.requests, "post") as post:
            post.return_value.raise_for_status.return_value = None
            self.assertTrue(atelier_app.send_telegram_reply("123", "hello"))
            self.assertIs(post.call_args.kwargs["allow_redirects"], False)

    def test_openrouter_request_disables_redirects_for_api_key_request(self):
        response = type("Response", (), {"status_code": 400, "text": "rejected", "headers": {}, "json": lambda self: {"error": {"message": "rejected"}}})()
        with patch.object(atelier_app, "OPENROUTER_API_KEY", "test-key"), patch.object(atelier_app.requests, "post", return_value=response) as post:
            with self.assertRaises(atelier_app.LLMError):
                atelier_app.llm_chat([{"role": "user", "content": "test"}], "test")
            self.assertIs(post.call_args.kwargs["allow_redirects"], False)
    def test_openrouter_http_error_does_not_expose_provider_response_body(self):
        response = type("Response", (), {})()
        response.status_code = 400
        response.text = "sensitive-provider-diagnostic-and-secret"
        with patch.object(atelier_app, "OPENROUTER_API_KEY", "test-key"):
            with patch.object(atelier_app.requests, "post", return_value=response):
                with self.assertRaises(atelier_app.LLMError) as raised:
                    atelier_app.llm_chat([{"role": "user", "content": "hello"}], label="security-test")
        self.assertIn("HTTP 400", str(raised.exception))
        self.assertNotIn("sensitive-provider-diagnostic-and-secret", str(raised.exception))
    def test_telegram_reply_uses_timeout_and_handles_network_failure(self):
        with patch.object(atelier_app, "TELEGRAM_TOKEN", "test-token"), \
             patch.object(atelier_app.requests, "post") as post:
            post.return_value.raise_for_status.return_value = None
            self.assertTrue(atelier_app.send_telegram_reply("123", "hello"))
            self.assertEqual(post.call_args.kwargs["timeout"], 10)
            post.side_effect = atelier_app.requests.Timeout("timeout")
            self.assertFalse(atelier_app.send_telegram_reply("123", "hello"))

    def test_active_job_configuration_is_bounded_and_fails_safe(self):
        self.assertEqual(atelier_app.parse_max_active_jobs("4"), 4)
        self.assertEqual(atelier_app.parse_max_active_jobs("0"), 1)
        self.assertEqual(atelier_app.parse_max_active_jobs("100"), 16)
        self.assertEqual(atelier_app.parse_max_active_jobs("-10"), 1)
        self.assertEqual(atelier_app.parse_max_active_jobs("invalid"), 4)

    def test_trusted_proxy_hops_configuration_is_bounded_and_fails_closed(self):
        self.assertEqual(atelier_app.parse_trusted_proxy_hops("1"), 1)
        self.assertEqual(atelier_app.parse_trusted_proxy_hops("5"), 5)
        self.assertEqual(atelier_app.parse_trusted_proxy_hops("99"), 5)
        self.assertEqual(atelier_app.parse_trusted_proxy_hops("-2"), 0)
        self.assertEqual(atelier_app.parse_trusted_proxy_hops("invalid"), 0)

    def test_telegram_webhook_is_disabled_by_default(self):
        with patch.object(atelier_app, "TELEGRAM_WEBHOOK_ENABLED", False):
            with atelier_app.app.test_request_context("/_tg_disabled", method="POST"):
                response = atelier_app.telegram_webhook()
        self.assertEqual(response[1], 404)

    def test_telegram_webhook_ignores_malformed_message_shapes(self):
        with patch.object(atelier_app, "TELEGRAM_WEBHOOK_ENABLED", True), \
             patch.object(atelier_app, "TELEGRAM_TOKEN", "test-token"), \
             patch.object(atelier_app, "TELEGRAM_WEBHOOK_SECRET", "expected-secret"):
            with atelier_app.app.test_request_context(
                "/test-token", method="POST", json={"message": {"chat": "invalid"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
            ):
                response = atelier_app.telegram_webhook()
        self.assertEqual(response, ("OK", 200))

    def test_telegram_webhook_does_not_process_non_owner_messages(self):
        with patch.object(atelier_app, "TELEGRAM_WEBHOOK_ENABLED", True), \
             patch.object(atelier_app, "TELEGRAM_TOKEN", "test-token"), \
             patch.object(atelier_app, "TELEGRAM_WEBHOOK_SECRET", "expected-secret"), \
             patch.object(atelier_app, "OWNER_TELEGRAM_ID", "123"), \
             patch.object(atelier_app, "Github") as github_client:
            with atelier_app.app.test_request_context(
                "/test-token", method="POST",
                json={"message": {"chat": {"id": 999}, "from": {"id": 999},
                                  "text": "file:app.py"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
            ):
                response = atelier_app.telegram_webhook()
        self.assertEqual(response, ("OK", 200))
        github_client.assert_not_called()

    def test_telegram_webhook_ignores_non_numeric_chat_id(self):
        with patch.object(atelier_app, "TELEGRAM_WEBHOOK_ENABLED", True), \
             patch.object(atelier_app, "TELEGRAM_TOKEN", "test-token"), \
             patch.object(atelier_app, "TELEGRAM_WEBHOOK_SECRET", "expected-secret"), \
             patch.object(atelier_app, "OWNER_TELEGRAM_ID", "123"), \
             patch.object(atelier_app, "Github") as github_client:
            with atelier_app.app.test_request_context(
                "/test-token", method="POST",
                json={"message": {"chat": {"id": {"nested": "value"}},
                                  "from": {"id": 123}, "text": "file:app.py"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
            ):
                response = atelier_app.telegram_webhook()
        self.assertEqual(response, ("OK", 200))
        github_client.assert_not_called()

    def test_telegram_webhook_ignores_oversized_message(self):
        with patch.object(atelier_app, "TELEGRAM_WEBHOOK_ENABLED", True), \
             patch.object(atelier_app, "TELEGRAM_TOKEN", "test-token"), \
             patch.object(atelier_app, "TELEGRAM_WEBHOOK_SECRET", "expected-secret"):
            with atelier_app.app.test_request_context(
                "/test-token", method="POST",
                json={"message": {"chat": {"id": 1}, "from": {"id": 1},
                                  "text": "x" * (atelier_app.MAX_TELEGRAM_MESSAGE_CHARS + 1)}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
            ):
                response = atelier_app.telegram_webhook()
        self.assertEqual(response, ("OK", 200))

    def test_telegram_webhook_rejects_missing_secret(self):
        with patch.object(atelier_app, "TELEGRAM_WEBHOOK_ENABLED", True), \
             patch.object(atelier_app, "TELEGRAM_TOKEN", "test-token"), \
             patch.object(atelier_app, "TELEGRAM_WEBHOOK_SECRET", "expected-secret"):
            with atelier_app.app.test_request_context("/test-token", method="POST", json={}):
                response = atelier_app.telegram_webhook()
        self.assertEqual(response[1], 403)

    def test_telegram_webhook_rejects_non_ascii_secret_without_server_error(self):
        with patch.object(atelier_app, "TELEGRAM_WEBHOOK_ENABLED", True), \
             patch.object(atelier_app, "TELEGRAM_TOKEN", "test-token"), \
             patch.object(atelier_app, "TELEGRAM_WEBHOOK_SECRET", "expected-secret"):
            with atelier_app.app.test_request_context(
                "/test-token", method="POST", json={},
                headers={"X-Telegram-Bot-Api-Secret-Token": "秘密"},
            ):
                response = atelier_app.telegram_webhook()
        self.assertEqual(response, ("", 403))

    def test_telegram_webhook_blocks_non_allowlisted_development_target(self):
        with patch.object(atelier_app, "TELEGRAM_WEBHOOK_ENABLED", True), \
             patch.object(atelier_app, "TELEGRAM_TOKEN", "test-token"), \
             patch.object(atelier_app, "TELEGRAM_WEBHOOK_SECRET", "expected-secret"), \
             patch.object(atelier_app, "REPO_NAME", "someone/another-repo"), \
             patch.object(atelier_app, "BRANCH", "visual-lab-rebuild"):
            with atelier_app.app.test_request_context(
                "/test-token", method="POST", json={},
                headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
            ):
                response = atelier_app.telegram_webhook()
        self.assertEqual(response[1], 403)

    def test_provider_network_error_does_not_expose_request_exception_details(self):
        secret = "sensitive-provider-transport-detail"
        with patch.object(atelier_app, "OPENROUTER_API_KEY", "test-key"):
            with patch.object(atelier_app.requests, "post", side_effect=atelier_app.requests.ConnectionError(secret)):
                with self.assertRaises(atelier_app.LLMError) as raised:
                    atelier_app.llm_chat([{"role": "user", "content": "test"}], "security-test")
        self.assertNotIn(secret, str(raised.exception))
        self.assertIn("network request failed", str(raised.exception))
    def test_telegram_webhook_processing_failure_does_not_log_exception_details(self):
        secret = "github-private-token-value"
        with patch.object(atelier_app, "TELEGRAM_WEBHOOK_ENABLED", True):
            with patch.object(atelier_app, "TELEGRAM_TOKEN", "telegram-token"):
                with patch.object(atelier_app, "TELEGRAM_WEBHOOK_SECRET", "webhook-secret"):
                    with patch.object(atelier_app, "OWNER_TELEGRAM_ID", "123"):
                        with patch.object(atelier_app, "GITHUB_TOKEN", "github-token"):
                            with patch.object(atelier_app.Auth, "Token", side_effect=RuntimeError(secret)):
                                with patch.object(atelier_app, "send_telegram_reply", return_value=False):
                                    with atelier_app.app.test_request_context(
                                        "/telegram-token", method="POST",
                                        json={"message": {"chat": {"id": 123}, "from": {"id": 123}, "text": "hello"}},
                                        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
                                    ):
                                        with self.assertLogs(atelier_app.app.logger, level="WARNING") as captured:
                                            response = atelier_app.telegram_webhook()
        self.assertEqual(response, ("OK", 200))
        self.assertNotIn(secret, "\n".join(captured.output))
    def test_telegram_reply_does_not_log_token_bearing_request_exception(self):
        token = "123456:telegram-secret-token"
        with patch.object(atelier_app, "TELEGRAM_TOKEN", token):
            with patch.object(atelier_app.requests, "post", side_effect=atelier_app.requests.ConnectionError("failed https://api.telegram.org/bot" + token + "/sendMessage")):
                with self.assertLogs(atelier_app.app.logger, level="WARNING") as captured:
                    self.assertFalse(atelier_app.send_telegram_reply(12345, "test"))
        self.assertNotIn(token, "\n".join(captured.output))
    def test_telegram_repository_path_validation_rejects_traversal_and_absolute_paths(self):
        for path in ("../app.py", "src/../../secret", "/etc/passwd", "src" + chr(92) + "app.py", ".git/config", "src//app.py"):
            with self.subTest(path=path):
                self.assertIsNone(atelier_app.validate_telegram_repo_path(path))

    def test_telegram_repository_path_validation_accepts_normal_relative_paths(self):
        self.assertEqual(atelier_app.validate_telegram_repo_path("atelier_engine/vision_lab.py"), "atelier_engine/vision_lab.py")
        self.assertEqual(atelier_app.validate_telegram_repo_path("app.py"), "app.py")
    def test_telegram_webhook_blocks_production_target(self):
        with patch.object(atelier_app, "TELEGRAM_WEBHOOK_ENABLED", True), \
             patch.object(atelier_app, "TELEGRAM_TOKEN", "test-token"), \
             patch.object(atelier_app, "TELEGRAM_WEBHOOK_SECRET", "expected-secret"), \
             patch.object(atelier_app, "REPO_NAME", "LokeshofficialGit/boutique-prompt"), \
             patch.object(atelier_app, "BRANCH", "main"):
            with atelier_app.app.test_request_context(
                "/test-token", method="POST", json={},
                headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
            ):
                response = atelier_app.telegram_webhook()
        self.assertEqual(response[1], 403)

    def test_active_job_limit_is_enforced_atomically(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
            with patch.object(atelier_app, "MAX_ACTIVE_JOBS", 1):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    results = list(pool.map(
                        lambda _: atelier_app.new_job("test", "balanced"),
                        range(24),
                    ))
            accepted = [job_id for job_id in results if job_id is not None]
            self.assertEqual(len(accepted), 1)
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_optimize_rejects_non_object_json_without_creating_job(self):
        original_key = atelier_app.OPENROUTER_API_KEY
        atelier_app.OPENROUTER_API_KEY = "test-key"
        try:
            with patch.object(atelier_app, "new_job") as new_job:
                response = self.client.post("/optimize", json=["not", "an", "object"])
                self.assertEqual(response.status_code, 400)
                self.assertIn("JSON object", response.get_json()["error"])
                new_job.assert_not_called()
        finally:
            atelier_app.OPENROUTER_API_KEY = original_key

    def test_optimize_rejects_non_text_prompt_without_creating_job(self):
        original_key = atelier_app.OPENROUTER_API_KEY
        atelier_app.OPENROUTER_API_KEY = "test-key"
        try:
            with patch.object(atelier_app, "new_job") as new_job:
                response = self.client.post("/optimize", json={"skeleton": {"unexpected": "object"}})
                self.assertEqual(response.status_code, 400)
                self.assertIn("must be text", response.get_json()["error"])
                new_job.assert_not_called()
        finally:
            atelier_app.OPENROUTER_API_KEY = original_key

    def test_job_retention_prunes_finished_jobs_but_keeps_active_jobs(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
            with patch.object(atelier_app, "MAX_ACTIVE_JOBS", 30):
                active_id = atelier_app.new_job("active", "balanced")
                for index in range(25):
                    finished_id = atelier_app.new_job("finished", "balanced")
                    atelier_app.set_job(finished_id, status="done", prompt=f"result-{index}")
            with atelier_app.jobs_lock:
                self.assertIn(active_id, atelier_app.jobs)
                self.assertLessEqual(len(atelier_app.jobs), atelier_app.MAX_JOBS_KEPT)
                self.assertTrue(all(
                    job["status"] == "running" or job["status"] == "done"
                    for job in atelier_app.jobs.values()
                ))
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_abandoned_running_job_times_out_and_releases_capacity(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
            with patch.object(atelier_app, "MAX_ACTIVE_JOBS", 1), patch.object(
                atelier_app, "MAX_JOB_RUNTIME_SECONDS", 60
            ):
                job_id = atelier_app.new_job("stuck", "balanced")
                with atelier_app.jobs_lock:
                    atelier_app.jobs[job_id]["created"] -= 61
                replacement = atelier_app.new_job("replacement", "balanced")
                self.assertIsNotNone(replacement)
                snapshot = atelier_app.get_job_snapshot(job_id)
                self.assertEqual(snapshot["status"], "error")
                self.assertIn("too long", snapshot["error"])
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_late_worker_result_cannot_overwrite_timed_out_job(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs["stale"] = {"status": "error", "created": atelier_app.time.time(), "error": "timed out"}
            atelier_app.set_job("stale", status="done", prompt="late result")
            self.assertEqual(atelier_app.get_job_snapshot("stale")["status"], "error")
            self.assertIsNone(atelier_app.get_job_snapshot("stale").get("prompt"))
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_legacy_terminal_job_with_null_finished_at_uses_created_time(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs["legacy"] = {
                    "status": "done",
                    "created": 100,
                    "finished_at": None,
                }
                atelier_app.evict_finished_jobs(now=150)
                self.assertIn("legacy", atelier_app.jobs)
                atelier_app.evict_finished_jobs(now=100 + atelier_app.FINISHED_JOB_TTL_SECONDS + 1)
                self.assertNotIn("legacy", atelier_app.jobs)
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_timeout_starts_finished_retention_at_timeout(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs["stuck"] = {
                    "status": "running",
                    "created": 10,
                    "finished_at": None,
                }
                timeout_at = 10 + atelier_app.MAX_JOB_RUNTIME_SECONDS + 1
                atelier_app.evict_finished_jobs(now=timeout_at)
                timed_out = atelier_app.jobs["stuck"]
                self.assertEqual(timed_out["status"], "error")
                self.assertEqual(timed_out["finished_at"], timeout_at)
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_finished_job_retention_starts_when_job_finishes(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
            with patch.object(atelier_app, "FINISHED_JOB_TTL_SECONDS", 60):
                job_id = atelier_app.new_job("completed-later", "balanced")
                created_at = atelier_app.jobs[job_id]["created"]
                finished_at = created_at + 500
                with patch.object(atelier_app.time, "time", return_value=finished_at):
                    atelier_app.set_job(job_id, status="done", prompt="result")
                self.assertEqual(atelier_app.jobs[job_id]["finished_at"], finished_at)
                atelier_app.evict_finished_jobs(now=finished_at + 30)
                self.assertIn(job_id, atelier_app.jobs)
                atelier_app.evict_finished_jobs(now=finished_at + 61)
                self.assertNotIn(job_id, atelier_app.jobs)
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_finished_job_ttl_removes_old_results(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs["old"] = {"status": "done", "created": 1, "prompt": "private result"}
                atelier_app.jobs["active"] = {"status": "running", "created": 1}
            with patch.object(atelier_app, "FINISHED_JOB_TTL_SECONDS", 60), patch.object(
                atelier_app, "MAX_JOB_RUNTIME_SECONDS", 3600
            ):
                atelier_app.evict_finished_jobs(now=100)
                self.assertNotIn("old", atelier_app.jobs)
                self.assertIn("active", atelier_app.jobs)
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_failed_worker_start_releases_reserved_job_slot(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
            job_id = atelier_app.new_job("test", "balanced")
            with patch.object(atelier_app, "WorkerThread", side_effect=RuntimeError("thread limit")):
                started = atelier_app.start_job_worker(job_id, lambda: None, ())
            self.assertFalse(started)
            self.assertNotIn(job_id, atelier_app.jobs)
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_job_snapshot_does_not_share_nested_mutable_values(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
            job_id = atelier_app.new_job("test", "balanced")
            atelier_app.set_job(job_id, reference_analysis={"sections": ["look"]})
            snapshot = atelier_app.get_job_snapshot(job_id)
            snapshot["reference_analysis"]["sections"].append("mutated")
            with atelier_app.jobs_lock:
                stored = atelier_app.jobs[job_id]["reference_analysis"]["sections"]
            self.assertEqual(stored, ["look"])
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_vision_lab_job_does_not_expose_internal_value_errors(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
            job_id = atelier_app.new_job("vision_lab", "balanced")
            with patch.object(
                atelier_app, "run_vision_lab_pipeline",
                side_effect=ValueError("internal provider secret detail"),
            ):
                atelier_app.run_vision_lab_job(job_id, {"mode": "basic"})
            with atelier_app.jobs_lock:
                error = atelier_app.jobs[job_id]["error"]
            self.assertNotIn("internal provider secret detail", error)
            self.assertIn("review the inputs", error)
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_job_access_response_is_captured_before_worker_start(self):
        import inspect
        for route in (
            atelier_app.generate,
            atelier_app.optimize,
            atelier_app.synthesize_scratch,
            atelier_app.vision_lab_generate,
        ):
            source = inspect.getsource(route)
            self.assertLess(source.index("access_response = job_access_response(job_id)"),
                            source.index("start_job_worker("))
            self.assertIn("jsonify(access_response)", source)

    def test_job_status_rejects_malformed_identifiers(self):
        for malformed_id in ("not-a-uuid", "A" * 32, "a" * 31):
            response = self.client.get("/status/" + malformed_id)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_job_status_requires_matching_access_token(self):
        original_jobs = atelier_app.jobs.copy()
        try:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
            job_id = atelier_app.new_job("test", "balanced")
            token = atelier_app.job_access_token(job_id)
            second_job_id = atelier_app.new_job("test", "balanced")
            second_token = atelier_app.job_access_token(second_job_id)
            self.assertGreaterEqual(len(token), 40)
            self.assertNotEqual(token, second_token)
            denied = self.client.get("/status/" + job_id)
            self.assertEqual(denied.status_code, 404)
            self.assertEqual(denied.headers.get("Cache-Control"), "no-store")
            wrong = self.client.get("/status/" + job_id, headers={"Authorization": "Bearer wrong"})
            self.assertEqual(wrong.status_code, 404)
            allowed = self.client.get("/status/" + job_id, headers={"Authorization": "Bearer " + token})
            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(allowed.headers.get("Cache-Control"), "no-store")
            self.assertEqual(allowed.headers.get("Pragma"), "no-cache")
            self.assertNotIn("access_token", allowed.get_json())
        finally:
            with atelier_app.jobs_lock:
                atelier_app.jobs.clear()
                atelier_app.jobs.update(original_jobs)

    def test_oversized_generate_request_returns_json_error(self):
        with patch.object(atelier_app, "OPENROUTER_API_KEY", "test-key"):
            response = self.client.post(
                "/generate",
                data=b"subject_text=" + b"x" * (10 * 1024 * 1024),
                content_type="application/x-www-form-urlencoded",
            )
        self.assertEqual(response.status_code, 413)
        self.assertIn("10 MB", response.get_json()["error"])

    def test_security_headers_are_present_on_application_responses(self):
        response = self.client.get("/")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(
            response.headers.get("Permissions-Policy"),
            "camera=(), microphone=(), geolocation=()",
        )

    def test_vision_lab_validation_route_enforces_rate_limit(self):
        client = atelier_app.app.test_client()
        response = None
        for _ in range(31):
            response = client.post(
                "/vision-lab/validate",
                json={"prompt": "test", "instructions": "", "target_model_id": ""},
                environ_base={"REMOTE_ADDR": "198.51.100.42"},
            )
        self.assertEqual(response.status_code, 429)
        self.assertIn("Too many requests", response.get_json()["error"])
        self.assertEqual(response.mimetype, "application/json")

    def test_vision_lab_routes_are_registered_for_imported_app(self):
        rules = {rule.rule for rule in atelier_app.app.url_map.iter_rules()}
        self.assertIn("/vision-lab/generate", rules)
        self.assertIn("/vision-lab/repair", rules)


if __name__ == "__main__":
    unittest.main()
