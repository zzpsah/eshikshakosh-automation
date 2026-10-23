"""Isolated lifecycle regression tests; never contact the e-ShikshaKosh portal."""
from __future__ import annotations

import importlib.util
import json
import queue
import subprocess
import threading
import tempfile
import unittest
import zipfile
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

    @staticmethod
    def make_xlsx(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/><Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/></Types>")
            archive.writestr("xl/workbook.xml", "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheets><sheet name=\"Report\" sheetId=\"1\"/></sheets></workbook>")
            archive.writestr("xl/worksheets/sheet1.xml", "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData><row r=\"1\"><c r=\"A1\" t=\"inlineStr\"><is><t>Report fixture</t></is></c></row></sheetData></worksheet>")
        return path

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
        self.make_xlsx(expected)
        self.make_xlsx(unrelated)
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
        self.make_xlsx(first)
        self.make_xlsx(second)
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


    def test_valid_workbook_passes_integrity_validation(self):
        workbook = self.make_xlsx(self.exports / "valid.xlsx")
        self.assertEqual(jobserver.validate_workbook(workbook), (True, "ok"))

    def test_corrupt_workbook_is_rejected(self):
        workbook = self.exports / "corrupt.xlsx"
        workbook.write_bytes(b"not a zip workbook" * 20)
        valid, reason = jobserver.validate_workbook(workbook)
        self.assertFalse(valid)
        self.assertEqual(reason, "workbook is corrupt or unreadable")

    def test_workbook_outside_export_root_is_rejected(self):
        outside = Path(self.temp.name) / "outside.xlsx"
        self.make_xlsx(outside)
        valid, reason = jobserver.validate_workbook(outside)
        self.assertFalse(valid)
        self.assertEqual(reason, "output path is missing or outside the export directory")

    def test_runner_cannot_mark_corrupt_workbook_done(self):
        workbook = self.exports / "broken.xlsx"
        workbook.write_bytes(b"broken workbook" * 20)
        job = {"id": "broken-job", "workflow": "roster", "status": "running"}
        jobserver._jobs[job["id"]] = job
        result = subprocess.CompletedProcess([], 0, f"WORKBOOK={workbook}\n", "")
        with patch.object(jobserver, "build_command", return_value=([], {})), \
             patch.object(jobserver.subprocess, "run", return_value=result), \
             patch.object(jobserver, "_snapshot_exports", side_effect=[set(), {str(workbook)}]), \
             patch.object(jobserver, "audit"):
            jobserver._execute(job)
        self.assertEqual(job["status"], "failed")
        self.assertTrue(job["error"].startswith("invalid_output:"))
        self.assertIsNone(job.get("output"))

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


    def test_corrupt_state_file_is_preserved_without_overwriting_memory(self):
        jobserver.STATE_FILE.parent.mkdir(parents=True)
        original = b'{"broken": '
        jobserver.STATE_FILE.write_bytes(original)
        jobserver._jobs["sentinel"] = {"id": "sentinel", "status": "done"}
        jobserver.load_state()
        self.assertIn("sentinel", jobserver._jobs)
        self.assertEqual(jobserver.STATE_FILE.read_bytes(), original)

    def test_restart_requeues_waiting_jobs_in_creation_order_without_replaying_running_job(self):
        jobserver._job_queue = queue.Queue(maxsize=5)
        jobserver.STATE_FILE.parent.mkdir(parents=True)
        jobserver.STATE_FILE.write_text(json.dumps({
            # Deliberately reverse insertion order: recovery must use creation time.
            "new-waiting": {"id": "new-waiting", "status": "queued", "workflow": "roster", "created_at": 3},
            "interrupted": {"id": "interrupted", "status": "running", "workflow": "student", "created_at": 2},
            "old-waiting": {"id": "old-waiting", "status": "queued", "workflow": "student", "created_at": 1},
        }))
        jobserver.load_state()
        jobserver.recover_queued_jobs()
        self.assertEqual(jobserver._job_queue.get_nowait(), "old-waiting")
        jobserver._job_queue.task_done()
        self.assertEqual(jobserver._job_queue.get_nowait(), "new-waiting")
        jobserver._job_queue.task_done()
        self.assertTrue(jobserver._job_queue.empty())
        self.assertEqual(jobserver._jobs["interrupted"]["status"], "failed")
        self.assertEqual(jobserver._jobs["interrupted"]["error"], "interrupted_by_restart")

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
