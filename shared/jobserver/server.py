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
import os
import re
import subprocess
import threading
import time
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

# ------------------------------------------------------------- job store --

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def load_state() -> None:
    if STATE_FILE.exists():
        try:
            _jobs.update(json.loads(STATE_FILE.read_text()))
        except Exception:
            pass


def save_state() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_jobs, indent=2))
    tmp.replace(STATE_FILE)


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


def build_command(job: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    wf = job["workflow"]
    env = dict(os.environ)

    if wf == "student":
        cmd = [str(Path.home() / ".local/bin" / "eshikshakosh-report")]
        if job.get("class"):
            cmd += ["--class", job["class"]]
        if job.get("mode"):
            cmd += ["--mode", job["mode"]]
        if job.get("session"):
            cmd += ["--year", job["session"]]
        return cmd, env

    script = "run_teacher_report.sh" if wf == "roster" else "run_teacher_detail_report.sh"
    cmd = ["bash", str(REPO / "modules" / "teacher" / script), "--school", job["school"]]
    return cmd, env


_run_lock = threading.Lock()


def run_job(job_id: str) -> None:
    job = _jobs[job_id]
    job["status"] = "running"
    job["started_at"] = time.time()
    save_state()

    # The runners move files out of the repo root and into ~/exports, so two
    # concurrent runs would race on the same workbooks. Serialize execution.
    with _run_lock:
        _execute(job)


def _execute(job: dict[str, Any]) -> None:
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

        output: str | None = None
        if job["workflow"] == "student":
            m = re.search(r"^REPORT_READY=(.+)$", proc.stdout, re.M)
            if m:
                output = m.group(1).strip()
        if not output and new_files:
            output = new_files[-1]

        if proc.returncode != 0:
            job["status"] = "failed"
            job["error"] = f"runner exited {proc.returncode}"
        elif output and Path(output).is_file():
            job["status"] = "done"
            job["output"] = output
        else:
            job["status"] = "failed"
            job["error"] = "no output file produced"
    except subprocess.TimeoutExpired:
        job["status"] = "failed"
        job["error"] = "timeout"
    except Exception as exc:  # noqa: BLE001 - report any failure to the caller
        job["status"] = "failed"
        job["error"] = type(exc).__name__

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

        job_id = hashlib.sha256(
            f"{time.time()}{workflow}{json.dumps(job, sort_keys=True)}".encode()
        ).hexdigest()[:16]
        job.update(
            id=job_id,
            status="queued",
            created_at=time.time(),
            output=None,
            error=None,
        )
        with _lock:
            _jobs[job_id] = job
        save_state()
        audit("job_created", job=job_id, workflow=workflow)

        threading.Thread(target=run_job, args=(job_id,), daemon=True).start()
        self._json(201, {"id": job_id, "status": "queued"})

    # -- job views -------------------------------------------------------

    def _get_job(self, job_id: str) -> None:
        job = _jobs.get(job_id)
        if not job:
            self._json(404, {"error": "not found"})
            return
        self._json(200, job)

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
