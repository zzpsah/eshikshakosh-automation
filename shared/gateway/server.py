#!/usr/bin/env python3
"""School Data Desk — private report gateway.

Runs on the Oracle VPS. It is the only thing the Vercel application talks to,
and it is the only thing that knows the job service bearer token:

    GET  /healthz                public liveness
    GET  /v1/config              app capabilities (schools, workflows)
    POST /v1/reports             start a report job
    GET  /v1/reports/<id>        job status — never a filesystem path
    GET  /dl/<signed-token>      single-use workbook download

Design:
- The app authenticates with an app token sent in the `x-report-token` header.
  Portal credentials, the job bearer token and workbook bytes never leave here.
- Downloads are HMAC-signed, single-use, short-TTL links. Job records handed to
  the browser carry a file name and size, never a server path.
- Finished jobs and their workbooks are deleted once the retention window passes.
- Binding a public address is refused unless `allow_public` is set in config.json,
  because that requires publishing the node's tailnet key and exposes student data.

`config.json` (operator-owned, mode 0600):
    {
      "app_token": "<high-entropy secret>",
      "job_token": "<job service bearer token>",
      "job_url": "http://127.0.0.1:8787",
      "download_ttl": 600,
      "retention_hours": 24,
      "max_jobs": 200,
      "allow_public": false
    }

Stdlib only — runs from the repository venv without touching requirements.txt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s gateway %(levelname)s %(message)s")
log = logging.getLogger("gateway")

REPO = Path(__file__).resolve().parent
CONFIG_FILE = REPO / "config.json"

DEFAULTS: dict[str, Any] = {
    "job_url": "http://127.0.0.1:8787",
    "download_ttl": 600,
    "retention_hours": 24,
    "output_root": str(Path.home() / "exports"),
    "max_jobs": 200,
    "allow_public": False,
    # Secrets are allowed through the loader but never written by this process
    # unless --init is run explicitly.
    "app_token": "",
    "job_token": "",
}

SCHOOLS = [
    {"key": "Sahaspur", "label": "UMV Sahaspur", "udise": "10130106304"},
    {"key": "Tetahali", "label": "UCHCH Madhyamik Vidyalaya Tetahali", "udise": "10160203806"},
]
SCHOOL_KEYS = [s["key"] for s in SCHOOLS]
CLASSES = ["", "9", "10", "11", "12"]
MODES = ["full", "masked"]
WORKFLOWS = {
    "student": {"name": "Student details", "tag": "OTR", "scope": "classes 9-12"},
    "roster": {"name": "Teacher roster", "tag": "LIST", "scope": "all teachers"},
    "detail": {"name": "Full teacher profiles", "tag": "DETAIL", "scope": "all teachers"},
}
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# ---------------------------------------------------------------- config --


def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    try:
        raw = json.loads(CONFIG_FILE.read_text())
        if isinstance(raw, dict):
            cfg.update({k: v for k, v in raw.items() if k in DEFAULTS})
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        log.warning("config unreadable: %s", type(exc).__name__)
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2) + "\n")
    os.chmod(tmp, 0o600)
    tmp.replace(CONFIG_FILE)


def _app_token() -> str:
    return str(load_config().get("app_token") or "")


# ------------------------------------------------------------- transport --


class GatewayError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _job_request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = load_config()
    token = str(cfg.get("job_token") or "")
    if not token:
        raise GatewayError(503, "Gateway is not configured.")
    url = f"{cfg['job_url'].rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError:
        log.warning("job service %s -> HTTP error", path)
        raise GatewayError(502, "Report service rejected the request.") from None
    except Exception as exc:  # noqa: BLE001
        log.warning("job service unreachable: %s", type(exc).__name__)
        raise GatewayError(502, "Report service unreachable.") from None


# -------------------------------------------------------- signing / links --

_sign_key = secrets.token_bytes(32)
_links: dict[str, dict[str, Any]] = {}
_links_lock = threading.Lock()


def _sign(value: str) -> str:
    return hmac.new(_sign_key, value.encode(), hashlib.sha256).hexdigest()[:32]


def issue_link(job_id: str, name: str) -> str:
    token = secrets.token_urlsafe(12)
    exp = int(time.time()) + int(load_config().get("download_ttl", 600))
    with _links_lock:
        _links[token] = {"job": job_id, "name": name, "exp": exp, "used": False}
    return f"{token}.{_sign(token)}"


def redeem_link(raw: str) -> str:
    token, _, sig = raw.partition(".")
    if not token or not hmac.compare_digest(sig, _sign(token)):
        raise GatewayError(404, "Not found.")
    with _links_lock:
        entry = _links.get(token)
        if not entry:
            raise GatewayError(404, "Not found.")
        if entry["used"] or entry["exp"] < time.time():
            _links.pop(token, None)
            raise GatewayError(410, "This download link has expired.")
        entry["used"] = True
        return str(entry["job"])


# ---------------------------------------------------------------- jobs ----

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _view(job: dict[str, Any]) -> dict[str, Any]:
    """Public job shape — never the server filesystem path."""
    out: dict[str, Any] = {
        "id": job["id"],
        "status": job["status"],
        "workflow": job["workflow"],
        "school": job.get("school"),
        "class": job.get("class"),
        "mode": job.get("mode"),
        "session": job.get("session"),
        "created_at": job.get("created_at"),
        "finished_at": job.get("finished_at"),
        "file_name": Path(job["output"]).name if job.get("output") else None,
        "file_bytes": None,
    }
    if job.get("output") and Path(job["output"]).is_file():
        out["file_bytes"] = Path(job["output"]).stat().st_size
    if job["status"] == "failed":
        out["error"] = job.get("error", "unknown error")
    if job["status"] == "done":
        out["download_url"] = issue_link(job["id"], out["file_name"] or "report.xlsx")
    return out


def _prune() -> None:
    """Delete finished jobs and their workbooks past the retention window.

    Two passes: jobs still tracked in memory, then a sweep of the output root by
    mtime. The sweep is what actually holds retention across a restart — the
    in-memory job list is lost on every restart, so without it orphaned workbooks
    accumulate forever.
    """
    cfg = load_config()
    horizon = time.time() - int(cfg.get("retention_hours", 24)) * 3600
    with _jobs_lock:
        stale = [
            jid
            for jid, job in _jobs.items()
            if job.get("status") in ("done", "failed") and job.get("finished_at", 0) < horizon
        ]
        for jid in stale:
            job = _jobs.get(jid)
            # Only remove the cache record after its workbook was safely handled.
            # Never let a cached path delete a file outside the configured root.
            if job and job.get("output"):
                try:
                    p = Path(job["output"]).resolve(strict=False)
                    root = Path(cfg.get("output_root") or (Path.home() / "exports")).expanduser().resolve()
                    if not p.is_relative_to(root):
                        log.warning("retention: refusing path outside output root for job %s", jid)
                        continue
                    if p.is_file():
                        if any(part.lower() == "archive" for part in p.relative_to(root).parts[:-1]):
                            continue
                        p.unlink()
                        log.info("retention: removed expired report for job %s", jid)
                except OSError as exc:
                    log.warning("retention: could not remove expired report (%s)", type(exc).__name__)
                    continue
            _jobs.pop(jid, None)
    if stale:
        log.info("retention: pruned %d job(s)", len(stale))
    _sweep_output_root(horizon, cfg)


REPORT_SUFFIXES = {".xlsx", ".csv", ".pdf", ".zip"}


def _sweep_output_root(horizon: float, cfg: dict[str, Any]) -> None:
    """Unlink report files older than `horizon` anywhere under the output root.

    Independent of in-memory job state, so it also reclaims workbooks whose job
    record was lost to a restart. Restricted to report extensions so unrelated
    files in the same directory are never touched.
    """
    root = Path(cfg.get("output_root") or (Path.home() / "exports")).expanduser().resolve()
    if not root.is_dir():
        return
    removed = 0
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in REPORT_SUFFIXES:
            continue
        # `archive/` holds historical workbooks that are kept permanently
        # (see modules/student/README.md) — never sweep them. Resolve first so
        # an archive symlink cannot escape the configured output root.
        try:
            relative = p.resolve(strict=True).relative_to(root)
        except (OSError, RuntimeError, ValueError):
            continue
        if p.is_symlink() or any(part.lower() == "archive" for part in relative.parts[:-1]):
            continue
        try:
            resolved = p.resolve(strict=True)
            # Symlinks and paths resolving outside the root are never cleanup targets.
            resolved.relative_to(root)
            if p.is_symlink():
                continue
            if p.stat().st_mtime < horizon:
                p.unlink()
                removed += 1
        except OSError as exc:
            log.warning("retention: could not remove %s (%s)", p.name, type(exc).__name__)
    if removed:
        log.info("retention: swept %d orphaned workbook(s) from %s", removed, root)


def _retention_loop() -> None:
    # Sweep immediately at startup: workbooks orphaned by a previous run are
    # reclaimed on boot rather than waiting a full interval.
    try:
        _prune()
    except Exception as exc:  # noqa: BLE001
        log.warning("retention sweep failed: %s", type(exc).__name__)
    while True:
        time.sleep(300)
        try:
            _prune()
        except Exception as exc:  # noqa: BLE001
            log.warning("retention sweep failed: %s", type(exc).__name__)


threading.Thread(target=_retention_loop, daemon=True).start()


def _create(body: dict[str, Any]) -> dict[str, Any]:
    workflow = body.get("workflow")
    if workflow not in WORKFLOWS:
        raise GatewayError(400, "Unknown workflow.")

    payload: dict[str, Any] = {"workflow": workflow}
    if workflow == "student":
        cls = str(body.get("class") or "")
        mode = str(body.get("mode") or "full")
        session = str(body.get("session") or "")
        if cls not in CLASSES:
            raise GatewayError(400, "Invalid class.")
        if mode not in MODES:
            raise GatewayError(400, "Invalid mode.")
        if session and (len(session) != 7 or session[4] != "-"):
            raise GatewayError(400, "Invalid session.")
        payload.update({"class": cls, "mode": mode, "session": session})
    else:
        school = str(body.get("school") or "")
        if school not in SCHOOL_KEYS:
            raise GatewayError(400, "Unknown school.")
        payload["school"] = school

    result = _job_request("POST", "/jobs", payload)
    job_id = result.get("id")
    if not job_id:
        raise GatewayError(502, "Report service did not return a job id.")

    cfg = load_config()
    with _jobs_lock:
        if len(_jobs) >= int(cfg.get("max_jobs", 200)):
            oldest = min(_jobs.items(), key=lambda kv: kv[1].get("created_at", 0))[0]
            _jobs.pop(oldest, None)
        _jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "created_at": time.time(),
            "finished_at": 0,
            "output": None,
            **payload,
        }
    log.info("job %s created (%s)", job_id, workflow)
    return _view(_jobs[job_id])


def _status(job_id: str) -> dict[str, Any]:
    # Job IDs are generated as 16 lowercase hex characters by the job service.
    # Validate before forwarding an unknown ID to the internal service.
    if len(job_id) != 16 or any(c not in "0123456789abcdef" for c in job_id):
        raise GatewayError(404, "Not found.")

    with _jobs_lock:
        job = _jobs.get(job_id)

    # The gateway cache is intentionally in-memory. After a gateway restart,
    # recover the record from the persistent job service instead of returning
    # 404 for a valid previously-created report.
    if job is None:
        fresh = _job_request("GET", f"/jobs/{job_id}")
        if fresh.get("id") != job_id:
            raise GatewayError(404, "Not found.")
        job = {
            "id": job_id,
            "status": fresh.get("status", "failed"),
            "workflow": fresh.get("workflow"),
            "school": fresh.get("school"),
            "class": fresh.get("class"),
            "mode": fresh.get("mode"),
            "session": fresh.get("session"),
            "created_at": fresh.get("created_at", time.time()),
            "finished_at": fresh.get("finished_at", 0),
            "output": fresh.get("output"),
            "error": fresh.get("error"),
        }
        with _jobs_lock:
            # Keep an entry that may have been added while the service request ran.
            job = _jobs.setdefault(job_id, job)
    elif job["status"] in ("queued", "running"):
        fresh = _job_request("GET", f"/jobs/{job_id}")
        with _jobs_lock:
            current = _jobs.get(job_id, job)
            current["status"] = fresh.get("status", current["status"])
            current["output"] = fresh.get("output")
            current["error"] = fresh.get("error")
            current["finished_at"] = fresh.get("finished_at") or current.get("finished_at", 0)
            job = current

    return _view(job)


# --------------------------------------------------------------- handler --

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class Handler(BaseHTTPRequestHandler):
    server_version = "SchoolDataDeskGateway/1.0"
    protocol_version = "HTTP/1.1"

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
        expected = _app_token()
        if not expected:
            return False
        header = self.headers.get("x-report-token", "")
        return bool(header) and hmac.compare_digest(header, expected)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            data = json.loads(self.rfile.read(length))
        except Exception:  # noqa: BLE001
            return {}
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        try:
            if path == "/healthz":
                self._json(200, {"ok": True})
                return
            if not self._authed():
                self._json(401, {"error": "Unauthorized."})
                return
            if path == "/v1/config":
                cfg = load_config()
                self._json(
                    200,
                    {
                        "schools": SCHOOLS,
                        "workflows": WORKFLOWS,
                        "classes": CLASSES,
                        "modes": MODES,
                        "session": "2026-27",
                        "download_ttl": int(cfg.get("download_ttl", 600)),
                    },
                )
                return
            if path.startswith("/v1/reports/"):
                self._json(200, _status(path[len("/v1/reports/") :]))
                return
            if path.startswith("/dl/"):
                self._download(path[len("/dl/") :])
                return
            self._json(404, {"error": "Not found."})
        except GatewayError as exc:
            self._json(exc.status, {"error": exc.detail})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        try:
            if path != "/v1/reports":
                self._json(404, {"error": "Not found."})
                return
            if not self._authed():
                self._json(401, {"error": "Unauthorized."})
                return
            self._json(201, _create(self._body()))
        except GatewayError as exc:
            self._json(exc.status, {"error": exc.detail})

    def _download(self, token: str) -> None:
        """Signed, single-use handoff. Still behind the app token: the link is
        only ever minted for an authenticated caller, so it never travels alone."""
        try:
            job_id = redeem_link(token)
        except GatewayError as exc:
            self._json(exc.status, {"error": exc.detail})
            return
        with _jobs_lock:
            job = _jobs.get(job_id)
            path = job.get("output") if job else None
        if not job or job.get("status") != "done" or not path:
            self._json(409, {"error": "Report is not ready."})
            return
        p = Path(path)
        if not p.is_file():
            self._json(410, {"error": "Report is no longer available."})
            return
        data = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", XLSX_TYPE)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{p.name}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        log.info("%s %s", self.client_address[0], format % args)


def main() -> None:
    import argparse
    import sys
    import uuid

    parser = argparse.ArgumentParser(description="School Data Desk private gateway")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--init", action="store_true", help="write a starter config.json")
    args = parser.parse_args()

    public = args.host not in LOCAL_HOSTS

    if args.init:
        cfg = load_config()
        if not cfg.get("app_token"):
            cfg["app_token"] = uuid.uuid4().hex + uuid.uuid4().hex
        if not cfg.get("job_token"):
            cfg["job_token"] = uuid.uuid4().hex + uuid.uuid4().hex
        cfg.setdefault("job_url", "http://127.0.0.1:8787")
        save_config(cfg)
        print(f"wrote {CONFIG_FILE} (mode 0600)")
        print("Next: set job_token to the real job service token, and allow_public if you really need a public bind.")
        return

    if public and not load_config().get("allow_public"):
        print("ERROR: refusing to bind a public address without config allow_public=true", file=sys.stderr)
        print("This gateway serves student data. Keep it tailnet-only behind a tunnel.", file=sys.stderr)
        sys.exit(2)

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    log.info("gateway listening on %s:%s", args.host, args.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
