"""Fail-closed startup tests for opt-in Redis job infrastructure."""
import os
import subprocess
import sys
import unittest


class JobQueueStartupConfigurationTests(unittest.TestCase):
    def run_app_import(self, *, queue_enabled=True, app_env="test", redis_url=None, ratelimit_url=None):
        env = os.environ.copy()
        env["JOB_QUEUE_ENABLED"] = "true" if queue_enabled else "false"
        env["APP_ENV"] = app_env
        if redis_url is None:
            env.pop("JOB_STORE_REDIS_URL", None)
        else:
            env["JOB_STORE_REDIS_URL"] = redis_url
        if ratelimit_url is None:
            env.pop("RATELIMIT_STORAGE_URI", None)
        else:
            env["RATELIMIT_STORAGE_URI"] = ratelimit_url
        return subprocess.run(
            [sys.executable, "-c", "import app"],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )


    def test_production_requires_tls_rate_limit_storage(self):
        result = self.run_app_import(queue_enabled=False, app_env="production")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires RATELIMIT_STORAGE_URI", result.stderr)
        self.assertIn("rediss://", result.stderr)

    def test_production_rate_limit_storage_rejects_plaintext_redis(self):
        result = self.run_app_import(
            queue_enabled=False,
            app_env="production",
            ratelimit_url="redis://localhost:6379/0",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TLS-protected rediss://", result.stderr)

    def test_production_rate_limit_storage_requires_authentication(self):
        result = self.run_app_import(
            queue_enabled=False,
            app_env="production",
            ratelimit_url="rediss://localhost:6379/0",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires Redis authentication", result.stderr)

    def test_enabled_queue_requires_redis_url(self):
        result = self.run_app_import()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires JOB_STORE_REDIS_URL", result.stderr)
        self.assertNotIn("local-only fallback", result.stdout)

    def test_production_queue_rejects_non_tls_redis_url_before_connecting(self):
        result = self.run_app_import(
            app_env="production",
            redis_url="redis://localhost:6379/15",
            ratelimit_url="rediss://default:test-password@localhost:6379/0",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires a TLS-protected rediss://", result.stderr)

    def test_production_queue_requires_redis_authentication(self):
        result = self.run_app_import(
            app_env="production",
            redis_url="rediss://localhost:6379/15",
            ratelimit_url="rediss://default:test-password@localhost:6379/0",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires Redis authentication", result.stderr)

    def test_unreachable_explicit_redis_does_not_fall_back_to_memory(self):
        result = self.run_app_import(redis_url="redis://127.0.0.1:1/15")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("InMemoryJobStore", result.stderr)
        self.assertNotIn("local-only fallback", result.stdout)


if __name__ == "__main__":
    unittest.main()
