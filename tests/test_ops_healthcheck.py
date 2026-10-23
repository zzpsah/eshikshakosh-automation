"""Read-only ops health-check tests; use synthetic state and mocked HTTP."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ops_healthcheck.py"
spec = importlib.util.spec_from_file_location("ops_healthcheck_under_test", MODULE_PATH)
ops = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(ops)


class OpsHealthcheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / "jobs.json"

    def tearDown(self):
        self.temp.cleanup()

    def write_state(self, jobs):
        self.state.write_text(json.dumps(jobs), encoding="utf-8")

    def test_healthy_job_summary_contains_aggregate_data_only(self):
        self.write_state({
            "secret-job-id": {"status": "done", "created_at": 990, "school": "private school", "password": "do-not-print"},
            "waiting-id": {"status": "queued", "created_at": 995, "output": "/private/report.xlsx"},
        })
        result = ops.summarize_jobs(self.state, now=1000)
        self.assertTrue(result["ok"])
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["by_status"], {"done": 1, "queued": 1})
        serialized = json.dumps(result)
        for sensitive in ("secret-job-id", "private school", "do-not-print", "report.xlsx"):
            self.assertNotIn(sensitive, serialized)

    def test_stale_queued_and_running_jobs_raise_alert_without_ids(self):
        self.write_state({
            "q-secret": {"status": "queued", "created_at": 100},
            "r-secret": {"status": "running", "created_at": 100},
        })
        result = ops.summarize_jobs(self.state, now=2000,
                                    queued_stale_seconds=1800,
                                    running_stale_seconds=1200)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stale_queued"], 1)
        self.assertEqual(result["stale_running"], 1)
        self.assertNotIn("q-secret", json.dumps(result))
        self.assertNotIn("r-secret", json.dumps(result))

    def test_missing_and_corrupt_state_are_safe_failures(self):
        self.assertEqual(ops.summarize_jobs(self.state)["error"], "state_file_missing")
        self.state.write_text('{bad json', encoding="utf-8")
        self.assertEqual(ops.summarize_jobs(self.state)["error"], "state_file_unreadable")

    def test_invalid_state_schema_is_rejected(self):
        self.state.write_text(json.dumps(["not", "a", "mapping"]), encoding="utf-8")
        self.assertEqual(ops.summarize_jobs(self.state)["error"], "state_schema_invalid")

    def test_probe_only_reports_status_not_response_body(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"ok":true,"password":"hidden"}'
        with patch.object(ops.urllib.request, "urlopen", return_value=Response()):
            result = ops.probe("http://127.0.0.1/health")
        self.assertEqual(result, {"ok": True, "http_status": 200})
        self.assertNotIn("hidden", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
