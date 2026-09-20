"""Read-only e-ShikshaKosh student report export.

Use a manually obtained, short-lived bearer token. This script never automates
password, CAPTCHA, OTP, or portal submission flows and never writes to the
portal. It masks sensitive values before writing an Excel workbook.
"""

from __future__ import annotations

import getpass
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

BASE_URL = "https://eshikshakosh.bihar.gov.in:8443"
LIST_URL = f"{BASE_URL}/student/viewStudentList"
DEFAULT_TIMEOUT_SECONDS = 60


def decode_jwt_claims(token: str) -> dict[str, Any]:
    """Read unsigned token claims only to obtain the school scope for the request."""
    import base64

    try:
        payload = token.removeprefix("Bearer").strip().split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (IndexError, ValueError, UnicodeDecodeError):
        return {}


def mask(value: Any, visible: int = 4) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    return "*" * max(0, len(value) - visible) + value[-visible:]


def normalise_record(record: dict[str, Any]) -> dict[str, Any]:
    """Retain non-sensitive fields and mask sensitive identifiers in exports."""
    sensitive = {"aadhaar", "aadhar", "account", "bankaccount", "mobile", "phone"}
    cleaned: dict[str, Any] = {}
    for key, value in record.items():
        compact_key = key.lower().replace("_", "").replace(" ", "")
        cleaned[key] = mask(value) if any(word in compact_key for word in sensitive) else value
    return cleaned


def fetch_student_pages(session: requests.Session, headers: dict[str, str], school_id: str, academic_year: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset, limit = 0, 500
    while True:
        payload = {"offset": str(offset), "limit": str(limit), "searchSchoolId": school_id, "academicYear": academic_year}
        response = session.post(LIST_URL, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        body = response.json()
        page = body.get("data") or body.get("content") or body.get("result") or []
        if isinstance(page, dict):
            page = page.get("content") or page.get("records") or []
        if not isinstance(page, list):
            raise RuntimeError("Unexpected portal response. No report was written.")
        records.extend(item for item in page if isinstance(item, dict))
        print(f"Fetched {len(records)} student record(s)…")
        if len(page) < limit:
            return records
        offset += limit


def main() -> None:
    print("e-ShikshaKosh read-only report export")
    print("Manual login only. Do not paste a password, OTP, or cookie here.")
    academic_year = input("Academic year [2026-27]: ").strip() or "2026-27"
    token = getpass.getpass("Paste a short-lived Bearer token: ").strip().removeprefix("Bearer").strip()
    if not token:
        raise RuntimeError("A bearer token is required; no request was sent.")

    claims = decode_jwt_claims(token)
    school_id = str(claims.get("sub") or "").strip()
    if not school_id:
        raise RuntimeError("The token did not provide a school scope; no request was sent.")

    headers = {"accept": "application/json, text/plain, */*", "content-type": "application/json", "authorization": f"Bearer {token}", "origin": "https://eshikshakosh.bihar.gov.in", "referer": "https://eshikshakosh.bihar.gov.in/"}
    session = requests.Session()  # TLS verification remains enabled.
    records = fetch_student_pages(session, headers, school_id, academic_year)
    frame = pd.DataFrame([normalise_record(record) for record in records])
    output = Path(f"Eshikshakosh_ReadOnly_Report_{academic_year}_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
    frame.to_excel(output, index=False)
    print(f"Created {output} with {len(frame)} masked record(s). Review before use.")


if __name__ == "__main__":
    main()
