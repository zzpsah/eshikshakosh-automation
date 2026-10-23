#!/usr/bin/env python3
"""School Data Desk job service.

A small authenticated HTTP service that runs the existing read-only report
workflows on the Oracle VPS and serves the resulting workbooks.

Security properties:
- Bearer token auth on every endpoint except /health (JOB_SERVER_TOKEN).
- Input allowlists for workflow / school / class / mode / session.
- Subprocess timeout on every runner.
- Rate limiting per client IP.
- Audit log records actions and outcomes only -- never secrets, tokens,
  or personal data.

The service never writes back to the e-ShikshaKosh portal. It only invokes
the existing read-only runners.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import importlib.util
import os
import queue
import re
import subprocess
import threading
import time
import zipfile
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- config --

REPO = Path.home() / "projects" / "eshikshakosh-automation"
EXPORTS = Path.home() / "exports"
STATE_FILE = Path.home() / ".local" / "share" / "jobserver" / "jobs.json"
AUDIT_LOG = Path.home() / ".local" / "share" / "jobserver" / "audit.log"

TOKEN = os.environ.get("JOB_SERVER_TOKEN", "")
HOST = os.environ.get("JOB_SERVER_HOST", "127.0.0.1")
PORT = int(os.environ.get("JOB_SERVER_PORT", "8787"))
TIMEOUT = int(os.environ.get("JOB_SERVER_TIMEOUT", "900"))

WORKFLOWS = {"student", "roster", "detail"}
SCHOOLS = {"Sahaspur", "Tetahali"}
CLASSES = {"", "9", "10", "11", "12"}
MODES = {"full", "masked"}
SESSION_RE = re.compile(r"^\d{4}-\d{2}$")
# Credentials authorize one run only. They are held in memory for the lifetime
# of the job and are stripped before anything is persisted or logged.
CREDENTIAL_FIELDS = ("username", "password")

# ------------------------------------------------------------- job store --

_lock = threading.RLock()
_jobs: dict[str, dict[str, Any]] = {}
MAX_QUEUED_JOBS = max(1, int(os.environ.get("JOB_SERVER_MAX_QUEUED", "50")))
_job_queue: queue.Queue[str] = queue.Queue(maxsize=MAX_QUEUED_JOBS)


def load_state() -> None:
    """Load persisted jobs and reconcile jobs interrupted by a service restart."""
    if not STATE_FILE.exists():
        return
    try:
        data = json.loads(STATE_FILE.read_text())
        if not isinstance(data, dict):
            return
        reconciled = False
        with _lock:
            _jobs.clear()
            for job_id, job in data.items():
                if not isinstance(job, dict):
                    continue
                if job.get("status") == "running":
                    job = dict(job)
                    job.update(
                        status="failed",
                        error="interrupted_by_restart",
                        finished_at=time.time(),
                    )
                    reconciled = True
                _jobs[str(job_id)] = job
        if reconciled:
            save_state()
    except (OSError, json.JSONDecodeError):
        # Keep the service available if state is temporarily unreadable; do not
        # overwrite the file here, because it may still be recoverable.
        return


def save_state() -> None:
    """Atomically persist one consistent snapshot of the job store.

    Credentials are excluded: they authorize a single run and must never be
    written to disk.
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with _lock:
        safe = {
            jid: {k: v for k, v in job.items() if k not in CREDENTIAL_FIELDS}
            for jid, job in _jobs.items()
        }
        payload = json.dumps(safe, indent=2)
        tmp.write_text(payload)
        tmp.replace(STATE_FILE)


def enqueue_job(job: dict[str, Any]) -> bool:
    """Persist and enqueue a job, returning False when the pending queue is full."""
    job_id = str(job["id"])
    with _lock:
        if _job_queue.full():
            return False
        _jobs[job_id] = job
        try:
            save_state()
        except OSError:
            _jobs.pop(job_id, None)
            raise
        # The worker takes the same store lock before looking up this ID, so it
        # cannot race ahead of the persisted record.
        _job_queue.put_nowait(job_id)
    return True


def recover_queued_jobs() -> None:
    """Restore queued work up to capacity; fail excess persisted jobs explicitly."""
    changed = False
    with _lock:
        waiting = sorted(
            ((job_id, job) for job_id, job in _jobs.items() if job.get("status") == "queued"),
            key=lambda item: (item[1].get("created_at", 0), item[0]),
        )
        for job_id, job in waiting:
            try:
                _job_queue.put_nowait(job_id)
            except queue.Full:
                job["status"] = "failed"
                job["error"] = "queue_capacity_exceeded_after_restart"
                job["finished_at"] = time.time()
                changed = True
        if changed:
            save_state()


def audit(action: str, **fields: Any) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.time(), "action": action}
    rec.update({k: v for k, v in fields.items() if v is not None})
    line = json.dumps(rec, default=str)
    with AUDIT_LOG.open("a") as fh:
        fh.write(line + "\n")


# ---------------------------------------------------------------- runner --

def _snapshot_exports() -> set[str]:
    if not EXPORTS.exists():
        return set()
    return {str(p) for p in EXPORTS.rglob("*") if p.is_file()}


def validate_workbook(path: str | Path) -> tuple[bool, str]:
    """Validate that a report is a readable XLSX workbook within exports."""
    try:
        candidate = Path(path).expanduser().resolve(strict=True)
        export_root = EXPORTS.resolve(strict=True)
        candidate.relative_to(export_root)
    except (OSError, RuntimeError, ValueError):
        return False, "output path is missing or outside the export directory"

    if candidate.suffix.lower() != ".xlsx":
        return False, "output is not an XLSX workbook"
    try:
        if not candidate.is_file() or candidate.stat().st_size < 100:
            return False, "workbook file is empty or too small"
        with zipfile.ZipFile(candidate, "r") as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                return False, "workbook structure is incomplete"
            sheet_files = sorted(
                name for name in names
                if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
            )
            if not sheet_files:
                return False, "workbook contains no worksheets"
            # Parse key XML parts so a truncated or malformed ZIP is not accepted.
            ET.fromstring(archive.read("[Content_Types].xml"))
            workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
            sheet_nodes = workbook_root.findall(".//{*}sheet")
            if not sheet_nodes or len(sheet_nodes) != len(sheet_files):
                return False, "workbook sheet metadata is inconsistent"
            for sheet_name in sheet_files:
                ET.fromstring(archive.read(sheet_name))
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError, RuntimeError):
        return False, "workbook is corrupt or unreadable"
    return True, "ok"


def school_udise(school_key: str) -> str | None:
    """Resolve a school key to its UDISE code via the shared registry."""
    registry = REPO / "shared" / "esk_schools.py"
    if not registry.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("esk_schools", registry)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:  # noqa: BLE001
        return None
    entry = mod.find(school_key)
    return entry["udise"] if entry else None


def build_command(job: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    wf = job["workflow"]
    env = dict(os.environ)
    # Inherited credentials would shadow a one-time login supplied with the job.
    env.pop("ESHIKSHAKOSH_USERNAME", None)
    env.pop("ESHIKSHAKOSH_PASSWORD", None)
    user = job.get("username")
    pwd = job.get("password")
    has_creds = bool(user and pwd)

    if wf == "student":
        if has_creds:
            # Direct one-time credentials: run the report without the Bitwarden
            # wrapper, which would otherwise overwrite these with stored secrets.
            env["ESHIKSHAKOSH_USERNAME"] = str(user)
            env["ESHIKSHAKOSH_PASSWORD"] = str(pwd)
            env["ESHIKSHAKOSH_EXPORT_MODE"] = job.get("mode") or "full"
            env["ESHIKSHAKOSH_CLASS"] = job.get("class") or ""
            if job.get("session"):
                env["ESHIKSHAKOSH_YEAR"] = job["session"]
            return ["bash", str(REPO / "modules" / "student" / "run_report.sh")], env
        cmd = [str(Path.home() / ".local/bin" / "eshikshakosh-report")]
        if job.get("class"):
            cmd += ["--class", job["class"]]
        if job.get("mode"):
            cmd += ["--mode", job["mode"]]
        if job.get("session"):
            cmd += ["--year", job["session"]]
        return cmd, env

    script = "run_teacher_report.sh" if wf == "roster" else "run_teacher_detail_report.sh"
    cmd = ["bash", str(REPO / "modules" / "teacher" / script)]
    if has_creds:
        # The teacher runner takes credentials from the environment, never argv,
        # so the password cannot appear in the process list.
        udise = school_udise(job["school"])
        if not udise:
            raise RuntimeError(f"no UDISE registered for school {job['school']!r}")
        env["ESHIKSHAKOSH_USERNAME"] = str(user)
        env["ESHIKSHAKOSH_PASSWORD"] = str(pwd)
        cmd += ["--udise", udise]
    else:
        cmd += ["--school", job["school"]]
    return cmd, env



def run_job(job_id: str) -> None:
    # Called only by the single queue worker. A job remains queued until the
    # worker actually starts it, so API polling reflects its real lifecycle.
    with _lock:
        job = _jobs.get(job_id)
        if not job or job.get("status") != "queued":
            return
        job["status"] = "running"
        job["started_at"] = time.time()
        save_state()
    _execute(job)


def _worker_loop() -> None:
    while True:
        job_id = _job_queue.get()
        try:
            run_job(job_id)
        except Exception as exc:  # keep one persistence/runtime failure from killing the worker
            with _lock:
                job = _jobs.get(job_id)
                if job and job.get("status") in {"queued", "running"}:
                    job["status"] = "failed"
                    job["error"] = f"worker_error:{type(exc).__name__}"
                    job["finished_at"] = time.time()
                    try:
                        save_state()
                    except OSError:
                        pass
            try:
                audit("job_worker_error", job=job_id, error=type(exc).__name__)
            except OSError:
                pass
        finally:
            _job_queue.task_done()


def _execute(job: dict[str, Any]) -> None:
    status = "failed"
    error: str | None = None
    output_path: str | None = None
    try:
        cmd, env = build_command(job)
        before = _snapshot_exports()
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        after = _snapshot_exports()
        new_files = sorted(after - before)

        # Each current runner emits an explicit machine-readable output marker.
        # Only use the filesystem delta as a compatibility fallback when exactly
        # one workbook appeared; never guess between multiple candidate reports.
        marker = "REPORT_READY" if job["workflow"] == "student" else (
            "WORKBOOK" if job["workflow"] in {"roster", "detail"} else ""
        )
        output: str | None = None
        if marker:
            matches = re.findall(rf"^{marker}=(.+)$", proc.stdout, re.M)
            if matches:
                output = matches[-1].strip()
        if not output:
            candidates = [p for p in new_files if Path(p).suffix.lower() == ".xlsx"]
            if len(candidates) == 1:
                output = candidates[0]

        if proc.returncode != 0:
            error = f"runner exited {proc.returncode}"
        elif output:
            valid, validation_error = validate_workbook(output)
            if valid:
                status = "done"
                output_path = str(Path(output).resolve())
            else:
                error = f"invalid_output: {validation_error}"
        elif not output and len([p for p in new_files if Path(p).suffix.lower() == ".xlsx"]) > 1:
            error = "ambiguous output files"
        else:
            error = "no output file produced"
    except subprocess.TimeoutExpired:
        error = "timeout"
    except Exception as exc:  # noqa: BLE001 - report any failure to the caller
        error = type(exc).__name__

    # Publish all terminal fields together so readers and persistence always see
    # a coherent state transition rather than a partially updated job record.
    with _lock:
        job["status"] = status
        job["error"] = error
        if output_path:
            job["output"] = output_path
        job["finished_at"] = time.time()
        save_state()
    audit("job_finished", job=job["id"], workflow=job["workflow"], status=job["status"])


# --------------------------------------------------------- rate limiting --

_rl_lock = threading.Lock()
_rl: dict[str, list[float]] = {}
RL_WINDOW = 60.0
RL_MAX = 20


def rate_limited(ip: str) -> bool:
    now = time.time()
    with _rl_lock:
        hits = [t for t in _rl.get(ip, []) if now - t < RL_WINDOW]
        hits.append(now)
        _rl[ip] = hits
        return len(hits) > RL_MAX


# ---------------------------------------------------------------- handler --

class Handler(BaseHTTPRequestHandler):
    server_version = "SchoolDataDesk/1.0"
    protocol_version = "HTTP/1.1"

    # -- helpers ---------------------------------------------------------

    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: Any) -> None:
        self._send(code, json.dumps(obj).encode())

    def _authed(self) -> bool:
        if not TOKEN:
            return False
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        return hmac.compare_digest(header[7:].strip(), TOKEN)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    # -- routes ----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"ok": True})
            return
        if not self._authed():
            self._json(401, {"error": "unauthorized"})
            return
        if rate_limited(self.client_address[0]):
            self._json(429, {"error": "rate limited"})
            return

        if self.path.startswith("/jobs/"):
            parts = self.path.split("/")
            if len(parts) == 3:
                self._get_job(parts[2])
                return
            if len(parts) == 4 and parts[3] == "download":
                self._download(parts[2])
                return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/jobs":
            self._json(404, {"error": "not found"})
            return
        if not self._authed():
            self._json(401, {"error": "unauthorized"})
            return
        if rate_limited(self.client_address[0]):
            self._json(429, {"error": "rate limited"})
            return

        data = self._body()
        workflow = data.get("workflow")
        if workflow not in WORKFLOWS:
            self._json(400, {"error": "unknown workflow"})
            return

        job: dict[str, Any] = {"workflow": workflow}

        if workflow == "student":
            cls = str(data.get("class") or "")
            mode = str(data.get("mode") or "full")
            session = str(data.get("session") or "")
            if cls not in CLASSES:
                self._json(400, {"error": "invalid class"})
                return
            if mode not in MODES:
                self._json(400, {"error": "invalid mode"})
                return
            if session and not SESSION_RE.match(session):
                self._json(400, {"error": "invalid session"})
                return
            job["class"] = cls
            job["mode"] = mode
            job["session"] = session
        else:
            school = str(data.get("school") or "")
            if school not in SCHOOLS:
                self._json(400, {"error": "unknown school"})
                return
            job["school"] = school

        # One-time credentials supplied by the operator. They are forwarded to
        # the runner as environment variables and never persisted or logged.
        username = data.get("username")
        password = data.get("password")
        if username is not None or password is not None:
            if not (
                isinstance(username, str)
                and isinstance(password, str)
                and username.strip()
                and password
            ):
                self._json(400, {"error": "username and password must be provided together"})
                return
            job["username"] = username.strip()
            job["password"] = password

        # Hash the non-secret fields only: the job ID must not be derived from a
        # credential, and two runs with identical inputs should collide-safe.
        identity = {k: v for k, v in job.items() if k not in CREDENTIAL_FIELDS}
        job_id = hashlib.sha256(
            f"{time.time()}{workflow}{json.dumps(identity, sort_keys=True)}".encode()
        ).hexdigest()[:16]
        job.update(
            id=job_id,
            status="queued",
            created_at=time.time(),
            output=None,
            error=None,
        )
        try:
            accepted = enqueue_job(job)
        except OSError:
            self._json(503, {"error": "job state unavailable"})
            return
        if not accepted:
            self._json(503, {"error": "job queue full; retry later"})
            return
        audit("job_created", job=job_id, workflow=workflow)
        self._json(201, {"id": job_id, "status": "queued"})

    # -- job views -------------------------------------------------------

    def _get_job(self, job_id: str) -> None:
        job = _jobs.get(job_id)
        if not job:
            self._json(404, {"error": "not found"})
            return
        # One-time credentials stay in the in-memory record only long enough for
        # the runner. Never expose them through the authenticated status API.
        public_job = {k: v for k, v in job.items() if k not in CREDENTIAL_FIELDS}
        self._json(200, public_job)

    def _download(self, job_id: str) -> None:
        job = _jobs.get(job_id)
        if not job:
            self._json(404, {"error": "not found"})
            return
        if job.get("status") != "done" or not job.get("output"):
            self._json(409, {"error": "not ready"})
            return
        path = Path(job["output"])
        if not path.is_file():
            self._json(410, {"error": "file gone"})
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.send_header("Content-Length", str(len(data)))
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{path.name}"',
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # -- logging ---------------------------------------------------------

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep the default access log but never let it carry request bodies.
        super().log_message(fmt, *args)


def main() -> None:
    if not TOKEN:
        raise SystemExit("JOB_SERVER_TOKEN is not set")
    load_state()
    # Requeue jobs accepted before a restart; jobs that were actively running
    # are marked failed by load_state and are not replayed automatically.
    recover_queued_jobs()
    threading.Thread(target=_worker_loop, name="jobserver-worker", daemon=True).start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    audit("server_start", host=HOST, port=PORT)
    print(f"jobserver listening on {HOST}:{PORT}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        audit("server_stop")


if __name__ == "__main__":
    main()
