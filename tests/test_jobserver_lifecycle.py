"""Isolated lifecycle regression tests; never contact the e-ShikshaKosh portal."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "shared" / "jobserver" / "server.py"
spec = importlib.util.spec_from_file_location("jobserver_under_test", MODULE_PATH)
jobserver = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(jobserver)


class JobLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.exports = root / "exports"
        self.exports.mkdir()
        jobserver.EXPORTS = self.exports
        jobserver.STATE_FILE = root / "state" / "jobs.json"
        jobserver.AUDIT_LOG = root / "state" / "audit.log"
        with jobserver._lock:
            jobserver._jobs.clear()
        while not jobserver._job_queue.empty():
            try:
                jobserver._job_queue.get_nowait()
                jobserver._job_queue.task_done()
            except Exception:
                break

    def tearDown(self):
        self.temp.cleanup()

    def test_restart_marks_running_failed_and_preserves_queued(self):
        jobserver.STATE_FILE.parent.mkdir(parents=True)
        jobserver.STATE_FILE.write_text(json.dumps({
            "active": {"id": "active", "status": "running", "workflow": "student"},
            "waiting": {"id": "waiting", "status": "queued", "workflow": "student"},
            "done": {"id": "done", "status": "done", "workflow": "student"},
        }))
        jobserver.load_state()
        self.assertEqual(jobserver._jobs["active"]["status"], "failed")
        self.assertEqual(jobserver._jobs["active"]["error"], "interrupted_by_restart")
        self.assertEqual(jobserver._jobs["waiting"]["status"], "queued")
        self.assertEqual(jobserver._jobs["done"]["status"], "done")

    def test_teacher_workbook_marker_wins_over_other_new_files(self):
        expected = self.exports / "Teacher_Details.xlsx"
        unrelated = self.exports / "unrelated.xlsx"
        expected.write_bytes(b"workbook fixture")
        unrelated.write_bytes(b"other fixture")
        job = {"id": "j1", "workflow": "detail", "status": "running"}
        before = set()
        result = subprocess.CompletedProcess([], 0, f"WORKBOOK={expected}\n", "")
        with patch.object(jobserver, "build_command", return_value=([], {})), \
             patch.object(jobserver.subprocess, "run", return_value=result), \
             patch.object(jobserver, "_snapshot_exports", side_effect=[before, {str(expected), str(unrelated)}]), \
             patch.object(jobserver, "audit"):
            jobserver._execute(job)
        self.assertEqual(job["status"], "done")
        self.assertEqual(Path(job["output"]), expected.resolve())

    def test_multiple_unmarked_workbooks_fail_instead_of_guessing(self):
        first = self.exports / "first.xlsx"
        second = self.exports / "second.xlsx"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        job = {"id": "j2", "workflow": "roster", "status": "running"}
        result = subprocess.CompletedProcess([], 0, "no marker\n", "")
        with patch.object(jobserver, "build_command", return_value=([], {})), \
             patch.object(jobserver.subprocess, "run", return_value=result), \
             patch.object(jobserver, "_snapshot_exports", side_effect=[set(), {str(first), str(second)}]), \
             patch.object(jobserver, "audit"):
            jobserver._execute(job)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"], "ambiguous output files")
        self.assertIsNone(job.get("output"))

    def test_queued_job_does_not_start_until_worker_picks_it_up(self):
        jobserver._jobs["queued-id"] = {
            "id": "queued-id", "status": "queued", "workflow": "student"
        }
        with patch.object(jobserver, "_execute") as execute:
            jobserver.run_job("queued-id")
        self.assertEqual(jobserver._jobs["queued-id"]["status"], "running")
        execute.assert_called_once_with(jobserver._jobs["queued-id"])


if __name__ == "__main__":
    unittest.main()
