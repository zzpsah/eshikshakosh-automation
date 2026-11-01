"""Fixed-school VidyaDesk status API exposes counts, never job records."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODULE = ROOT / "shared" / "jobserver" / "server.py"
spec = importlib.util.spec_from_file_location("jobserver_vidyadesk_status", MODULE)
jobserver = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(jobserver)


class HeaderMap(dict):
    def get(self, key, default=None):
        return super().get(key.lower(), default)


class VidyaDeskStatusTests(unittest.TestCase):
    def setUp(self):
        with jobserver._lock:
            jobserver._jobs.clear()
        self.old_token = jobserver.VIDYADESK_READ_TOKEN
        jobserver.VIDYADESK_READ_TOKEN = "dedicated-test-token"

    def tearDown(self):
        jobserver.VIDYADESK_READ_TOKEN = self.old_token
        with jobserver._lock:
            jobserver._jobs.clear()

    def test_fixed_school_summary_contains_only_aggregate_fields(self):
        with jobserver._lock:
            jobserver._jobs.update({
                "private-job-id": {"id": "private-job-id", "school": "Tetahali", "status": "done", "created_at": 990, "finished_at": 995, "password": "secret"},
                "queued-id": {"id": "queued-id", "school": "Tetahali", "status": "queued", "created_at": 995, "output": "/private/student.xlsx"},
                "other-school-id": {"id": "other-school-id", "school": "Sahaspur", "status": "failed", "created_at": 999},
            })
        result = jobserver._vidyadesk_status(now=1000)
        self.assertTrue(result["ok"])
        self.assertEqual(result["scope"], {"schoolKey": "umv-tetahali", "udiseCode": "10160203806"})
        self.assertEqual(result["totalJobs"], 2)
        self.assertEqual(result["byStatus"], {"queued": 1, "running": 0, "done": 1, "failed": 0, "other": 0})
        serialized = json.dumps(result)
        for private in ("private-job-id", "queued-id", "other-school-id", "secret", "student.xlsx", "Sahaspur"):
            self.assertNotIn(private, serialized)

    def test_stale_queued_and_running_jobs_are_flagged_without_ids(self):
        with jobserver._lock:
            jobserver._jobs.update({
                "q-secret": {"school": "Tetahali", "status": "queued", "created_at": 100},
                "r-secret": {"school": "Tetahali", "status": "running", "created_at": 200},
            })
        result = jobserver._vidyadesk_status(now=2000)
        self.assertFalse(result["ok"])
        self.assertEqual(result["staleQueued"], 1)
        self.assertEqual(result["staleRunning"], 1)
        self.assertNotIn("q-secret", json.dumps(result))
        self.assertNotIn("r-secret", json.dumps(result))

    def test_dedicated_token_is_not_the_existing_jobserver_bearer(self):
        request = object.__new__(jobserver.Handler)
        request.headers = HeaderMap({"x-vidyadesk-token": "dedicated-test-token"})
        self.assertTrue(request._vidyadesk_authed())
        request.headers = HeaderMap({"authorization": "Bearer jobserver-token"})
        self.assertFalse(request._vidyadesk_authed())
        request.headers = HeaderMap({"x-vidyadesk-token": "wrong"})
        self.assertFalse(request._vidyadesk_authed())

    def test_endpoint_fails_closed_when_dedicated_token_is_not_configured(self):
        request = object.__new__(jobserver.Handler)
        request.headers = HeaderMap({"x-vidyadesk-token": "anything"})
        with patch.object(jobserver, "VIDYADESK_READ_TOKEN", ""):
            self.assertFalse(request._vidyadesk_authed())

    def test_get_route_requires_token_and_returns_only_the_fixed_summary(self):
        response = {}
        request = object.__new__(jobserver.Handler)
        request.path = "/v1/integrations/vidyadesk/status"
        request.headers = HeaderMap({"x-vidyadesk-token": "dedicated-test-token"})
        request.client_address = ("127.0.0.1", 12345)
        request._json = lambda code, body: response.update(status=code, body=body)
        with patch.object(jobserver, "rate_limited", return_value=False), patch.object(
            jobserver, "_vidyadesk_status", return_value={"ok": True, "scope": {"schoolKey": "umv-tetahali"}}
        ) as summary:
            jobserver.Handler.do_GET(request)
        self.assertEqual(response, {"status": 200, "body": {"ok": True, "scope": {"schoolKey": "umv-tetahali"}}})
        summary.assert_called_once_with()

        response.clear()
        request.headers = HeaderMap({"authorization": "Bearer jobserver-token"})
        jobserver.Handler.do_GET(request)
        self.assertEqual(response, {"status": 401, "body": {"error": "unauthorized"}})


if __name__ == "__main__":
    unittest.main()
