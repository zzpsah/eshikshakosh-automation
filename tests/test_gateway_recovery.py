"""Gateway recovery tests use synthetic records and never contact the portal."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "shared" / "gateway" / "server.py"
spec = importlib.util.spec_from_file_location("gateway_under_test", MODULE_PATH)
gateway = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gateway)


class GatewayRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.output = root / "existing-report.xlsx"
        self.output.write_bytes(b"synthetic workbook fixture")
        self.config = root / "config.json"
        self.config.write_text(json.dumps({
            "app_token": "test-token",
            "job_token": "test-job-token",
            "job_url": "http://127.0.0.1:8787",
            "download_ttl": 600,
            "retention_hours": 24,
            "output_root": str(root),
            "max_jobs": 20,
            "allow_public": False,
        }))
        gateway.CONFIG_FILE = self.config
        with gateway._jobs_lock:
            gateway._jobs.clear()
        with gateway._links_lock:
            gateway._links.clear()

    def tearDown(self):
        self.temp.cleanup()

    def test_unknown_valid_job_is_recovered_from_job_service(self):
        job_id = "627aa8dc4cb2aaa6"
        record = {
            "id": job_id, "status": "done", "workflow": "roster",
            "school": "Tetahali", "created_at": 100, "finished_at": 200,
            "output": str(self.output), "error": None,
        }
        with patch.object(gateway, "_job_request", return_value=record) as request:
            result = gateway._status(job_id)
        request.assert_called_once_with("GET", f"/jobs/{job_id}")
        self.assertEqual(result["id"], job_id)
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["file_name"], self.output.name)
        self.assertEqual(result["file_bytes"], self.output.stat().st_size)
        self.assertTrue(result.get("download_url"))
        self.assertIn(job_id, gateway._jobs)

    def test_invalid_job_id_is_rejected_without_internal_request(self):
        with patch.object(gateway, "_job_request") as request:
            with self.assertRaises(gateway.GatewayError) as err:
                gateway._status("../../etc/passwd")
        self.assertEqual(err.exception.status, 404)
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
