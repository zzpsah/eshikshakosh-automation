#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eshikshakosh OTR — Local report generator (API-based) .

Login via Playwright → call viewStudentList with correct params →
export Excel with OTR, bank, Aadhaar data.

Supports --class, --section, --stream filters and optional split-sheet output.
"""

import argparse
import asyncio
import base64
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import nest_asyncio
import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from playwright.async_api import async_playwright
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("esk_otr")

BASE_URL = "https://eshikshakosh.bihar.gov.in:8443"
LIST_URL = f"{BASE_URL}/student/viewStudentList"
DETAIL_URL = f"{BASE_URL}/student/studentInfo"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def current_academic_year() -> str:
    """Return the current Indian school academic session as YYYY-YY (Apr-Mar)."""
    now = datetime.now()
    start_year = now.year if now.month >= 4 else now.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def safe_filename_component(value: str, fallback: str = "School") -> str:
    """Return a filesystem-safe compact filename component."""
    cleaned = "".join(
        ch if ch.isalnum() or ch in (" ", "-", "_") else " "
        for ch in str(value or "")
    )
    cleaned = "_".join(cleaned.split()).strip("._-")
    return cleaned or fallback


def decode_jwt(token: str) -> dict:
    try:
        clean = token.replace("Bearer", "").strip()
        parts = clean.split(".")
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception:
        return {}


def build_session(verify_ssl=False):
    s = requests.Session()
    s.verify = verify_ssl
    retries = Retry(total=4, backoff_factor=0.6,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["POST", "GET"])
    adapter = HTTPAdapter(max_retries=retries, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def build_headers(token: str, access_token: str) -> dict:
    return {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": "https://eshikshakosh.bihar.gov.in",
        "referer": "https://eshikshakosh.bihar.gov.in/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "authorization": f"Bearer {token}",
        "accesstoken": f"Bearer {access_token}",
        "authtoken": f"Bearer {token}",
        "authaccess": f"Bearer {access_token}",
    }

# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def login_playwright(uid: str, pwd: str) -> dict:
    captured = {}

    def find_tokens(value):
        if isinstance(value, dict):
            for key, item in value.items():
                key_l = str(key).lower().replace("-", "_")
                if key_l in {"token", "access_token", "accesstoken", "auth_token", "jwt"} and isinstance(item, str) and len(item) > 20:
                    yield key_l, item.replace("Bearer ", "").strip()
                yield from find_tokens(item)
        elif isinstance(value, list):
            for item in value:
                yield from find_tokens(item)

    async def on_response(resp):
        if "/auth/login" not in resp.url.lower():
            return
        captured["login_http_status"] = resp.status
        try:
            data = await resp.json()
        except Exception:
            captured["login_error"] = f"eShikshaKosh login returned HTTP {resp.status}"
            return

        if isinstance(data, dict):
            captured["login_response"] = data
            for key, value in find_tokens(data):
                captured.setdefault("token", value)
                if key in {"access_token", "accesstoken"}:
                    captured["access_token"] = value

            if captured.get("token"):
                log.info("eShikshaKosh login accepted (HTTP %s)", resp.status)
            else:
                message = str(data.get("msg") or data.get("message") or "").strip()
                captured["login_error"] = message or f"eShikshaKosh login rejected (HTTP {resp.status})"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage"])
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        page.on("response", on_response)

        await page.goto("https://eshikshakosh.bihar.gov.in",
                        wait_until="networkidle", timeout=35000)
        await page.click("#radio2")
        await page.wait_for_timeout(400)
        await page.fill("input[formcontrolname='userId']", uid)
        await page.fill("input[formcontrolname='password']", pwd)

        # Solve the portal's client-side multiplication/addition/subtraction CAPTCHA.
        captcha_text = await page.inner_text(".capcha__head")
        try:
            import re
            match = re.search(r"(\d+)\s*([+\-*])\s*(\d+)", captcha_text)
            if not match:
                raise ValueError("captcha expression not recognised")
            left, op, right = int(match.group(1)), match.group(2), int(match.group(3))
            answer = left + right if op == "+" else left - right if op == "-" else left * right
            captcha_answer = str(answer)
            log.info("Auto-solved captcha")
            await page.fill("input[placeholder='Enter User Captcha']", captcha_answer)
        except Exception as e:
            log.warning("Auto-captcha solve failed: %s", e)
            user_captcha = input("Enter captcha answer: ").strip()
            if user_captcha:
                await page.fill("input[placeholder='Enter User Captcha']", user_captcha)
            else:
                await browser.close()
                return {"login_error": "No CAPTCHA answer was provided."}

        await page.click("input.submit__btn")

        # The live portal returns the decisive result from /auth/login.
        for _ in range(80):
            if captured.get("token") or captured.get("login_error") or captured.get("login_http_status"):
                break
            await asyncio.sleep(0.25)

        # On success Angular stores the issued values in sessionStorage.
        if not captured.get("token") and not captured.get("login_error"):
            try:
                storage = await page.evaluate("Object.fromEntries(Object.entries(sessionStorage))")
                jwt_token = str(storage.get("jwtToken") or "").strip()
                access_token = str(storage.get("access_token") or "").strip()
                if jwt_token:
                    captured["token"] = jwt_token
                    captured["access_token"] = access_token or jwt_token
            except Exception as exc:
                log.warning("Post-login session inspection failed: %s", exc)

        captured["final_url"] = page.url
        await browser.close()

    return captured

# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def fetch_student_list(session, headers, school_id, school_enc_id,
                       district_id, block_id, cluster_id,
                       academic_year, offset=0, limit=100,
                       class_id="", stream="", section=""):
    payload = {
        "offset": str(offset),
        "limit": str(limit),
        "searchDistrictId": str(district_id),
        "searchBlockId": str(block_id),
        "searchClusterId": str(cluster_id),
        "searchSchoolId": str(school_id),
        "schoolEncId": school_enc_id,
        "studentCode": "",
        "admissionNo": "",
        "classId": str(class_id) if class_id else "",
        "stream": str(stream) if stream else "",
        "group": "",
        "section": str(section) if section else "",
    }
    res = session.post(LIST_URL, headers=headers, json=payload,
                       timeout=35, verify=False)
    if res.status_code != 200:
        log.warning("viewStudentList HTTP %d: %s",
                     res.status_code, res.text[:200])
        return [], 0
    data = res.json()
    return data.get("data", []), data.get("totalRecord", len(data.get("data", [])))


def fetch_student_detail(session, headers, enc_id, academic_year):
    try:
        res = session.post(DETAIL_URL, headers=headers,
                           json={"encId": enc_id, "academicYear": academic_year},
                           timeout=15, verify=False)
        if res.status_code == 200:
            return res.json().get("data", {})
    except Exception:
        pass
    return {}


# ---------------------------------------------------------------------------
# Bank resolution
# ---------------------------------------------------------------------------

IFSC_PREFIX_MAP = {
    "SBIN": "State Bank of India", "PUNB": "Punjab National Bank",
    "CBIN": "Central Bank of India", "UBIN": "Union Bank of India",
    "BKID": "Bank of India", "BARB": "Bank of Baroda",
    "CNRB": "Canara Bank", "UCOB": "UCO Bank",
    "IDIB": "Indian Bank", "IOBA": "Indian Overseas Bank",
    "IPOS": "India Post Payments Bank", "HDFC": "HDFC Bank",
    "ICIC": "ICICI Bank", "UTIB": "Axis Bank",
    "KKBK": "Kotak Mahindra Bank", "AIRP": "Airtel Payments Bank",
    "PYTM": "Paytm Payments Bank", "FINO": "Fino Payments Bank",
    "BDBL": "Bandhan Bank", "IBKL": "IDBI Bank",
    "YESB": "Yes Bank", "IDFB": "IDFC First Bank",
    "UBGB": "Uttar Bihar Gramin Bank", "DBGB": "Dakshin Bihar Gramin Bank",
}
BANK_CACHE = {"CBIN0R10001": "Uttar Bihar Gramin Bank",
              "IPOS0000001": "India Post Payments Bank"}

def mask_export_value(value, visible=4):
    text = str(value or "").strip()
    if not text:
        return ""
    return "*" * max(0, len(text) - visible) + text[-visible:]


def apply_export_mode(record: dict, export_mode: str) -> dict:
    if export_mode == "full":
        return record
    masked = dict(record)
    for key in ("Aadhaar Number", "Bank Account No", "Mobile Number"):
        if key in masked:
            masked[key] = mask_export_value(masked[key])
    return masked


def resolve_bank_name(ifsc: str) -> str:
    if not ifsc:
        return ""
    code = str(ifsc).strip().upper()
    if len(code) < 4:
        return ""
    if code in BANK_CACHE:
        return BANK_CACHE[code]
    try:
        r = requests.get(f"https://ifsc.razorpay.com/{code}", timeout=3)
        if r.status_code == 200:
            name = r.json().get("BANK", "")
            if name:
                BANK_CACHE[code] = name
                return name
    except Exception:
        pass
    return IFSC_PREFIX_MAP.get(code[:4], code[:4])


async def verify_only_async(udise, password, academic_year, verify_ssl=False):
    """Verify one live eShikshaKosh login and return non-secret school identity."""
    captured = await login_playwright(udise, password)
    token = captured.get("token")
    access_token = captured.get("access_token", token)
    if not token:
        detail = str(captured.get("login_error") or "No login token was returned.").strip()
        status = captured.get("login_http_status")
        if "invalid userid/password" in detail.lower():
            detail = "eShikshaKosh rejected the user ID/password."
        if status:
            raise RuntimeError(f"{detail} (HTTP {status})")
        raise RuntimeError(detail)

    jwt = decode_jwt(token)
    school_id = jwt.get("sub")
    school_enc_id = jwt.get("schoolEncId") or jwt.get("school") or ""
    district_id = jwt.get("district") or 16
    block_id = 219
    cluster_id = 2471
    user_profile = captured.get("login_response", {}).get("userProfile", "")
    if user_profile:
        try:
            profile = json.loads(user_profile)
            district_id = profile.get("district", district_id)
            block_id = profile.get("block", block_id)
            cluster_id = profile.get("cluster", cluster_id)
        except Exception:
            pass

    headers = build_headers(token, access_token)
    session = build_session(verify_ssl)
    batch, total = fetch_student_list(
        session, headers, school_id, school_enc_id,
        district_id, block_id, cluster_id,
        academic_year, 0, 1,
    )
    school_name = ""
    if batch:
        school_name = str(batch[0].get("schoolName") or "").strip()
    return {
        "verified": True,
        "udise": str(udise),
        "school_id": str(school_id or ""),
        "school_name": school_name or ("School " + str(udise)),
        "student_count": int(total or len(batch)),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main_async(udise, password, academic_year, output, verify_ssl,
                     export_mode="full", class_filter="", section_filter="",
                     stream_filter="", split_sheets=False):
    log.info("Logging in as UDISE %s ...", udise)
    captured = await login_playwright(udise, password)
    token = captured.get("token")
    access_token = captured.get("access_token", token)
    if not token:
        detail = str(captured.get("login_error") or "No login token was returned.").strip()
        status = captured.get("login_http_status")
        if "invalid userid/password" in detail.lower():
            detail = "eShikshaKosh rejected the saved user ID/password. Reconnect eShikshaKosh and enter the current portal password."
        if status:
            raise RuntimeError(f"{detail} (HTTP {status})")
        raise RuntimeError(detail)

    jwt = decode_jwt(token)
    school_id = jwt.get("sub")
    school_enc_id = jwt.get("schoolEncId") or jwt.get("school") or ""
    district_id = jwt.get("district") or 16

    # Try to extract block/cluster from userProfile
    block_id = 219   # Barharia (default for Siwan)
    cluster_id = 2471  # U.M.S. Barharia (default)
    user_profile = captured.get("login_response", {}).get("userProfile", "")
    if user_profile:
        try:
            profile = json.loads(user_profile)
            district_id = profile.get("district", district_id)
            block_id = profile.get("block", block_id)
            cluster_id = profile.get("cluster", cluster_id)
        except Exception:
            pass

    log.info("School ID: %s | Enc ID: %s | District: %d | Block: %d | Cluster: %d",
             school_id, (school_enc_id[:20] + "...") if school_enc_id else "N/A",
             district_id, block_id, cluster_id)

    headers = build_headers(token, access_token)
    session = build_session(verify_ssl)

    # Build filter description for logging
    filters = []
    if class_filter:
        filters.append(f"Class={class_filter}")
    if section_filter:
        filters.append(f"Section={section_filter}")
    if stream_filter:
        filters.append(f"Stream={stream_filter}")
    filter_desc = ", ".join(filters) if filters else "None (all students)"
    log.info("Filters: %s", filter_desc)

    # Fetch student list
    log.info("Fetching student list from viewStudentList...")
    all_students = []
    offset = 0
    limit = 100
    total = None

    while True:
        batch, total = fetch_student_list(
            session, headers, school_id, school_enc_id,
            district_id, block_id, cluster_id,
            academic_year, offset, limit,
            class_id=class_filter, stream=stream_filter, section=section_filter)
        if not batch:
            break
        all_students.extend(batch)
        log.info("Loaded %d students (total: %s)", len(all_students), total or "?")
        if total and len(all_students) >= total:
            break
        if len(batch) < limit:
            break
        offset += limit

    if not all_students:
        log.error("No students found (filters may be too restrictive)")
        sys.exit(1)

    school_name = all_students[0].get("schoolName") or f"School_{udise}"
    log.info("School: %s | Total: %d", school_name, len(all_students))

    # Fetch details in parallel
    log.info("Fetching student details (mother, bank, IFSC, OTR)...")
    student_details = {}

    def get_detail(s):
        enc = s.get("studentId")
        code = s.get("studentCode")
        if not enc:
            return code, {}
        return code, fetch_student_detail(session, headers, enc, academic_year)

    with ThreadPoolExecutor(max_workers=16) as pool:
        for code, detail in pool.map(get_detail, all_students):
            student_details[code] = detail

    log.info("Details fetched for %d students", len(student_details))

    # Build records
    STREAM_MAP = {1: "Arts", 2: "Science", 3: "Commerce", 0: "N/A"}
    records = []

    for idx, s in enumerate(all_students, 1):
        code = str(s.get("studentCode") or "").strip()
        dt = student_details.get(code, {})

        mother = str(dt.get("motherName") or s.get("motherName") or "").strip()
        if mother in ("None", "null", ""):
            mother = ""

        father = str(dt.get("fatherName") or s.get("fatherName") or "").strip()

        bank_acc = str(dt.get("bankAccNo") or s.get("bankAccNo") or "").strip()
        if bank_acc in ("None", "null", "0", ""):
            bank_acc = ""
        ifsc = str(dt.get("IFSC") or s.get("IFSC") or "").strip().upper()
        if ifsc in ("None", "null", ""):
            ifsc = ""
        bank_name = resolve_bank_name(ifsc) if ifsc else ""
        acc_holder = str(dt.get("accHolderName") or s.get("accHolderName") or "").strip()
        if acc_holder in ("None", "null", ""):
            acc_holder = ""

        # Aadhaar — use unmasked from API directly
        aadhaar = str(s.get("aadhaar") or dt.get("aadhaar") or "").strip()
        if aadhaar in ("None", "null", ""):
            masked = s.get("maskedAadhaar") or dt.get("maskedAadhaar") or ""
            aadhaar = "" if masked in ("--", "None", "null") else str(masked)

        otr_no = str(s.get("otrNo") or dt.get("otrNo") or "").strip()
        if otr_no in ("None", "null", "0", ""):
            otr_no = ""
        otr_flag = s.get("otrFlag") or dt.get("otrFlag")
        otr_status = "Registered" if (otr_no or str(otr_flag) == "1") else "Pending"

        s_class = s.get("class")
        stream_val = s.get("stream") if s.get("stream") is not None else dt.get("stream")
        stream_text = STREAM_MAP.get(stream_val, str(stream_val) if stream_val is not None else "N/A")
        if str(s_class) not in ("11", "12"):
            stream_text = "N/A"

        cwsn_val = s.get("cwsn") or dt.get("cwsn")
        cwsn_text = "Yes" if str(cwsn_val) in ("1", "2") else "No"
        prof_status = s.get("stdProfileUpdatedStatus") or dt.get("stdProfileUpdatedStatus")
        profile_updated = "Yes" if str(prof_status) == "1" else "No"

        gender = str(s.get("gender"))
        gender_text = "Male" if gender == "1" else "Female" if gender == "2" else ""

        records.append(apply_export_mode({
            "S.No.": idx,
            "Student Name": str(s.get("studentName") or dt.get("studentName") or "").strip(),
            "Student Code": code,
            "Father's Name": father,
            "Mother's Name": mother,
            "Class": str(s.get("className") or (f"Class {s_class}" if s_class else "")).strip(),
            "Section": str(s.get("section") or "").strip(),
            "Roll No": str(s.get("rollNo") or "").strip(),
            "OTR Number": otr_no,
            "OTR Status": otr_status,
            "Aadhaar Number": aadhaar,
            "Bank Account No": bank_acc,
            "IFSC Code": ifsc,
            "Bank Name": bank_name,
            "Account Holder Name": acc_holder,
            "Mobile Number": str(s.get("mobile") or "").strip(),
            "DOB": str(s.get("dob") or dt.get("dob") or "").strip(),
            "Gender": gender_text,
            "Social Category": str(s.get("socialCategory") or "").strip(),
            "Admission No": str(s.get("admissionNo") or "").strip(),
            "Admission Date": str(s.get("admissionDate") or "").strip(),
            "Stream": stream_text,
            "CWSN": cwsn_text,
            "Profile Updated": profile_updated,
            "School Name": school_name,
            "UDISE": udise,
            "Academic Year": academic_year,
        }, export_mode))

    # Write Excel
    if not output:
        school_part = safe_filename_component(school_name, fallback=str(udise))
        session_part = safe_filename_component(academic_year, fallback="Session")
        # Add filter info to filename
        filter_parts = []
        if class_filter:
            filter_parts.append(f"Class{class_filter}")
        if section_filter:
            filter_parts.append(f"Sec{section_filter}")
        if stream_filter:
            filter_parts.append(f"Stream{stream_filter}")
        filter_suffix = "_".join(filter_parts) if filter_parts else "All"
        output = f"Student_Details_{school_part}_{session_part}_{filter_suffix}.xlsx"

    columns = list(records[0].keys())
    wb = Workbook()
    default_ws = wb.active

    hfill = PatternFill(start_color="F2F4F7", end_color="F2F4F7", fill_type="solid")
    hfont = Font(name="Calibri", size=10, bold=True, color="1F2937")
    cfont = Font(name="Calibri", size=10, color="111827")
    border = Border(left=Side(style="thin", color="D1D5DB"),
                    right=Side(style="thin", color="D1D5DB"),
                    top=Side(style="thin", color="D1D5DB"),
                    bottom=Side(style="thin", color="D1D5DB"))
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    TEXT_COLS = ["Student Code", "Roll No", "OTR Number", "Aadhaar Number",
                 "Bank Account No", "IFSC Code", "Mobile Number",
                 "Admission No", "UDISE"]
    text_idx = [columns.index(c) + 1 for c in TEXT_COLS if c in columns]
    CENTER_COLS = ["S.No.", "Class", "Section", "Roll No", "OTR Number",
                   "OTR Status", "Aadhaar Number", "Bank Account No",
                   "IFSC Code", "Mobile Number", "DOB", "Gender",
                   "Social Category", "Admission Date", "Stream",
                   "CWSN", "Profile Updated", "UDISE", "Academic Year"]
    center_idx = [columns.index(c) + 1 for c in CENTER_COLS if c in columns]

    def write_sheet(ws, sheet_records):
        ws.append(columns)
        ws.row_dimensions[1].height = 25
        for cell in ws[1]:
            cell.fill = hfill
            cell.font = hfont
            cell.alignment = center
            cell.border = border
        for ri, rec in enumerate(sheet_records, 2):
            ws.row_dimensions[ri].height = 20
            ws.append([rec[c] for c in columns])
            for ci in range(1, len(columns) + 1):
                cell = ws.cell(row=ri, column=ci)
                cell.font = cfont
                cell.border = border
                if ci in text_idx:
                    cell.number_format = "@"
                    if cell.value is not None:
                        cell.value = str(cell.value).strip()
                cell.alignment = center if ci in center_idx else left
        for col in ws.columns:
            letter = get_column_letter(col[0].column)
            ws.column_dimensions[letter].width = min(max(max(len(str(c.value or "")) for c in col) + 4, 13), 42)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    if split_sheets and not (class_filter or section_filter or stream_filter):
        groups = {}
        for rec in records:
            cls = str(rec.get("Class", "")).replace("Class ", "").strip() or "Unknown"
            sec = str(rec.get("Section", "")).strip() or "All"
            stream_name = str(rec.get("Stream", "")).strip() or "N-A"
            if cls in ("11", "12") and stream_name not in ("N/A", "N-A", ""):
                key = (cls, sec, stream_name)
                title = f"C{cls}-S{sec}-{stream_name}"
            else:
                key = (cls, sec, "")
                title = f"C{cls}-S{sec}"
            groups.setdefault((key, title), []).append(rec)
        first = True
        for (_, title), group_records in sorted(groups.items(), key=lambda x: x[0][0]):
            safe_title = title[:31]
            ws = default_ws if first else wb.create_sheet()
            first = False
            ws.title = safe_title
            write_sheet(ws, group_records)
    else:
        default_ws.title = "Student OTR Roster"
        write_sheet(default_ws, records)

    wb.save(output)
    log.info("Saved: %s", output)

    # Summary
    reg = sum(1 for r in records if r["OTR Status"] == "Registered")
    pend = len(records) - reg
    aad = sum(1 for r in records if r["Aadhaar Number"])
    bk = sum(1 for r in records if r["Bank Account No"])
    mom = sum(1 for r in records if r["Mother's Name"])
    print(f"\n{'='*60}")
    print(f"  Report: {output}")
    print(f"  Export Mode: {export_mode.upper()}")
    print(f"  Filters: {filter_desc}")
    print(f"  Total Students: {len(records)}")
    print(f"  OTR Registered: {reg}")
    print(f"  OTR Pending:    {pend}")
    print(f"  Aadhaar Count:  {aad}")
    print(f"  Bank Accounts:  {bk}")
    print(f"  Mother Names:   {mom}")
    print(f"{'='*60}")


def main():
    import os
    parser = argparse.ArgumentParser(
        description="Eshikshakosh OTR Report Generator (local) ")
    parser.add_argument("--udise", "-u", default=None,
                        help="Portal User ID / School UDISE (or set ESHIKSHAKOSH_USERNAME env var)")
    parser.add_argument("--password", "-p", default=None,
                        help="Portal password (or set ESHIKSHAKOSH_PASSWORD env var)")
    parser.add_argument("--year", "-y", default=current_academic_year(),
                        help="Academic year (default: current Apr-Mar session)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output Excel file")
    parser.add_argument("--verify-ssl", action="store_true",
                        help="Enable SSL verification")
    parser.add_argument("--export-mode", choices=["full", "masked"], default="full",
                        help="Export privacy mode (default: full)")
    # NEW: Filter arguments
    parser.add_argument("--class", "-c", dest="class_filter", default="",
                        help="Filter by class (e.g., 11, 12). Empty = all classes")
    parser.add_argument("--section", "-s", default="",
                        help="Filter by section (e.g., 1, 2). Empty = all sections")
    parser.add_argument("--stream", "-st", default="",
                        help="Filter by stream (1=Arts, 2=Science, 3=Commerce). Empty = all streams")
    parser.add_argument("--split-sheets", action="store_true",
                        help="Write all fetched students into class/section/stream-wise Excel sheets")
    parser.add_argument("--verify-only", action="store_true",
                        help="Verify login and print non-secret school identity only")
    args = parser.parse_args()

    # Fallback to env vars if CLI args not provided
    if not args.udise:
        args.udise = os.environ.get("ESHIKSHAKOSH_USERNAME", "")
    if not args.password:
        args.password = os.environ.get("ESHIKSHAKOSH_PASSWORD", "")

    if not args.udise:
        parser.error("--udise is required (or set ESHIKSHAKOSH_USERNAME env var)")
    if not args.password:
        import getpass
        args.password = getpass.getpass("Password: ")

    try:
        if args.verify_only:
            result = asyncio.get_event_loop().run_until_complete(
                verify_only_async(args.udise, args.password, args.year, args.verify_ssl)
            )
            print("VERIFY_OK=" + json.dumps(result, ensure_ascii=False))
        else:
            asyncio.get_event_loop().run_until_complete(
                main_async(args.udise, args.password, args.year,
                           args.output, args.verify_ssl, args.export_mode,
                           class_filter=args.class_filter,
                           section_filter=args.section,
                           stream_filter=args.stream,
                           split_sheets=args.split_sheets))
    except RuntimeError as exc:
        log.error("%s", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
