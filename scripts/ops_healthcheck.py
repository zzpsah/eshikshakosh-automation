#!/usr/bin/env python3
"""Read-only operational health check for the report gateway and jobserver.

Prints aggregate status only. Never emits job IDs, school names, filenames,
request bodies, credentials, or persisted job error text.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_GATEWAY_HEALTH = "http://127.0.0.1:8790/healthz"
DEFAULT_JOBSERVER_HEALTH = "http://127.0.0.1:8787/health"
DEFAULT_STATE_FILE = Path.home() / ".local" / "share" / "jobserver" / "jobs.json"


def probe(url: str, timeout: float = 2.0) -> dict[str, Any]:
    """Return sanitized HTTP health result without response body details."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            try:
                payload = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            healthy = response.status == 200 and isinstance(payload, dict) and payload.get("ok") is True
            return {"ok": healthy, "http_status": response.status}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "http_status": int(exc.code)}
    except Exception as exc:  # noqa: BLE001 - expose only the exception class
        return {"ok": False, "error_type": type(exc).__name__}


def summarize_jobs(state_file: Path, *, now: float | None = None,
                   queued_stale_seconds: float = 1800,
                   running_stale_seconds: float = 1200) -> dict[str, Any]:
    """Summarize persisted jobs without returning record-level information."""
    timestamp = time.time() if now is None else now
    try:
        raw = json.loads(state_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"ok": False, "error": "state_file_missing"}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": False, "error": "state_file_unreadable"}
    if not isinstance(raw, dict) or any(not isinstance(job, dict) for job in raw.values()):
        return {"ok": False, "error": "state_schema_invalid"}

    counts = Counter(str(job.get("status", "unknown")) for job in raw.values())
    queued_ages: list[float] = []
    running_ages: list[float] = []
    for job in raw.values():
        status = job.get("status")
        created = job.get("created_at")
        if not isinstance(created, (int, float)):
            continue
        age = max(0.0, timestamp - float(created))
        if status == "queued":
            queued_ages.append(age)
        elif status == "running":
            running_ages.append(age)

    stale_queued = sum(age >= queued_stale_seconds for age in queued_ages)
    stale_running = sum(age >= running_stale_seconds for age in running_ages)
    return {
        "ok": stale_queued == 0 and stale_running == 0,
        "total": len(raw),
        "by_status": {key: counts[key] for key in sorted(counts)},
        "stale_queued": stale_queued,
        "stale_running": stale_running,
        "oldest_queued_seconds": round(max(queued_ages), 1) if queued_ages else None,
        "oldest_running_seconds": round(max(running_ages), 1) if running_ages else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-url", default=DEFAULT_GATEWAY_HEALTH)
    parser.add_argument("--jobserver-url", default=DEFAULT_JOBSERVER_HEALTH)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--queued-stale-seconds", type=float, default=1800)
    parser.add_argument("--running-stale-seconds", type=float, default=1200)
    args = parser.parse_args()

    result = {
        "gateway": probe(args.gateway_url),
        "jobserver": probe(args.jobserver_url),
        "jobs": summarize_jobs(
            args.state_file,
            queued_stale_seconds=args.queued_stale_seconds,
            running_stale_seconds=args.running_stale_seconds,
        ),
    }
    result["ok"] = all(result[key]["ok"] for key in ("gateway", "jobserver", "jobs"))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
