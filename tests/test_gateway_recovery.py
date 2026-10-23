"""Gateway recovery tests use synthetic records and never contact the portal."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import os
import time
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


    def test_queued_job_status_refreshes_after_service_completes(self):
        job_id = "1111222233334444"
        queued = {"id": job_id, "status": "queued", "workflow": "roster", "created_at": 100, "output": None}
        done = {"id": job_id, "status": "done", "workflow": "roster", "created_at": 100, "finished_at": 200, "output": str(self.output)}
        with patch.object(gateway, "_job_request", side_effect=[queued, done]) as request:
            first = gateway._status(job_id)
            second = gateway._status(job_id)
        self.assertEqual(first["status"], "queued")
        self.assertIsNone(first["download_url"] if "download_url" in first else None)
        self.assertEqual(second["status"], "done")
        self.assertTrue(second["download_url"])
        request.assert_any_call("GET", f"/jobs/{job_id}")
        self.assertEqual(request.call_count, 2)

    def test_download_links_are_single_use_and_not_reusable_after_gateway_restart(self):
        job_id = "aabbccddeeff0011"
        old_link = gateway.issue_link(job_id, self.output.name)
        self.assertEqual(gateway.redeem_link(old_link), job_id)
        with gateway._links_lock:
            gateway._links.clear()  # simulate process restart: in-memory links are lost
        with self.assertRaises(gateway.GatewayError) as err:
            gateway.redeem_link(old_link)
        self.assertEqual(err.exception.status, 404)
        fresh_link = gateway.issue_link(job_id, self.output.name)
        self.assertEqual(gateway.redeem_link(fresh_link), job_id)
        with self.assertRaises(gateway.GatewayError) as err:
            gateway.redeem_link(fresh_link)
        self.assertEqual(err.exception.status, 410)


    def test_retention_sweep_removes_only_expired_report_files(self):
        root = Path(self.temp.name)
        old_file = root / "old.xlsx"
        recent_file = root / "recent.xlsx"
        archive_dir = root / "archive"
        archive_dir.mkdir()
        archived_file = archive_dir / "old.xlsx"
        unrelated_file = root / "notes.txt"
        for path in (old_file, recent_file, archived_file, unrelated_file):
            path.write_bytes(b"fixture")
        old_time = time.time() - 172800
        os.utime(old_file, (old_time, old_time))
        os.utime(archived_file, (old_time, old_time))
        os.utime(unrelated_file, (old_time, old_time))
        gateway._sweep_output_root(time.time() - 3600, {"output_root": str(root)})
        self.assertFalse(old_file.exists())
        self.assertTrue(recent_file.exists())
        self.assertTrue(archived_file.exists())
        self.assertTrue(unrelated_file.exists())

    def test_retention_refuses_cached_output_outside_root(self):
        root = Path(self.temp.name) / "exports"
        root.mkdir()
        cfg = json.loads(self.config.read_text())
        cfg["output_root"] = str(root)
        self.config.write_text(json.dumps(cfg))
        outside = Path(self.temp.name) / "keep.xlsx"
        outside.write_bytes(b"must be preserved")
        old = time.time() - 172800
        os.utime(outside, (old, old))
        with gateway._jobs_lock:
            gateway._jobs["old-job"] = {
                "id": "old-job", "status": "done", "finished_at": old,
                "output": str(outside), "created_at": old,
            }
        gateway._prune()
        self.assertTrue(outside.exists())
        self.assertIn("old-job", gateway._jobs)

    def test_retention_does_not_delete_historical_archive_from_cached_job(self):
        root = Path(self.temp.name) / "exports"
        root.mkdir()
        cfg = json.loads(self.config.read_text())
        cfg["output_root"] = str(root)
        self.config.write_text(json.dumps(cfg))
        archive = root / "archive"
        archive.mkdir(parents=True)
        historical = archive / "historical.xlsx"
        historical.write_bytes(b"archive fixture")
        old = time.time() - 172800
        os.utime(historical, (old, old))
        with gateway._jobs_lock:
            gateway._jobs["archive-job"] = {
                "id": "archive-job", "status": "done", "finished_at": old,
                "output": str(historical), "created_at": old,
            }
        gateway._prune()
        self.assertTrue(historical.exists())

    def test_invalid_job_id_is_rejected_without_internal_request(self):
        with patch.object(gateway, "_job_request") as request:
            with self.assertRaises(gateway.GatewayError) as err:
                gateway._status("../../etc/passwd")
        self.assertEqual(err.exception.status, 404)
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
