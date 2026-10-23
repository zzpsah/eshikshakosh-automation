"""Isolated lifecycle regression tests; never contact the e-ShikshaKosh portal."""
from __future__ import annotations

import importlib.util
import json
import queue
import subprocess
import threading
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
        jobserver._job_queue = queue.Queue(maxsize=jobserver.MAX_QUEUED_JOBS)

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
        persisted = json.loads(jobserver.STATE_FILE.read_text())
        self.assertEqual(persisted["active"]["status"], "failed")
        self.assertEqual(persisted["active"]["error"], "interrupted_by_restart")

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


    def test_queue_capacity_rejects_new_jobs_without_persisting_them(self):
        jobserver._job_queue = queue.Queue(maxsize=1)
        first = {"id": "first", "status": "queued", "workflow": "student"}
        second = {"id": "second", "status": "queued", "workflow": "student"}
        self.assertTrue(jobserver.enqueue_job(first))
        self.assertFalse(jobserver.enqueue_job(second))
        self.assertIn("first", jobserver._jobs)
        self.assertNotIn("second", jobserver._jobs)
        saved = json.loads(jobserver.STATE_FILE.read_text())
        self.assertEqual(list(saved), ["first"])

    def test_concurrent_enqueue_keeps_state_valid_and_all_accepted_within_capacity(self):
        results = []
        result_lock = threading.Lock()
        def submit(i):
            accepted = jobserver.enqueue_job({"id": f"job-{i}", "status": "queued", "workflow": "student"})
            with result_lock:
                results.append(accepted)
        threads = [threading.Thread(target=submit, args=(i,)) for i in range(20)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sum(results), 20)
        persisted = json.loads(jobserver.STATE_FILE.read_text())
        self.assertEqual(len(persisted), 20)
        self.assertEqual(set(persisted), {f"job-{i}" for i in range(20)})

    def test_runner_timeout_is_recorded_as_terminal_failure(self):
        job = {"id": "timeout-job", "workflow": "student", "status": "running"}
        jobserver._jobs[job["id"]] = job
        with patch.object(jobserver, "build_command", return_value=([], {})), \
             patch.object(jobserver.subprocess, "run", side_effect=subprocess.TimeoutExpired("runner", 1)), \
             patch.object(jobserver, "audit"):
            jobserver._execute(job)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"], "timeout")
        self.assertIsNotNone(job.get("finished_at"))
        self.assertEqual(json.loads(jobserver.STATE_FILE.read_text())["timeout-job"]["error"], "timeout")

    def test_nonzero_runner_exit_is_recorded_as_terminal_failure(self):
        job = {"id": "exit-job", "workflow": "student", "status": "running"}
        jobserver._jobs[job["id"]] = job
        result = subprocess.CompletedProcess([], 7, "", "synthetic failure")
        with patch.object(jobserver, "build_command", return_value=([], {})), \
             patch.object(jobserver.subprocess, "run", return_value=result), \
             patch.object(jobserver, "_snapshot_exports", side_effect=[set(), set()]), \
             patch.object(jobserver, "audit"):
            jobserver._execute(job)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"], "runner exited 7")

    def test_restart_recovery_marks_queued_jobs_over_capacity_failed(self):
        jobserver._job_queue = queue.Queue(maxsize=1)
        with jobserver._lock:
            jobserver._jobs.update({
                "one": {"id": "one", "status": "queued", "workflow": "student"},
                "two": {"id": "two", "status": "queued", "workflow": "student"},
            })
        jobserver.recover_queued_jobs()
        self.assertEqual(jobserver._jobs["one"]["status"], "queued")
        self.assertEqual(jobserver._jobs["two"]["status"], "failed")
        self.assertEqual(jobserver._jobs["two"]["error"], "queue_capacity_exceeded_after_restart")

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
