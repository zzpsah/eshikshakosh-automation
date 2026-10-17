#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EshikshaKosh Teacher Report Generator (API-based).

Login via Playwright → call /teacher/viewTeacher + /teacher/getTeacherDetails →
export Excel with full teacher details.

Reuses the proven student-report pattern (esk_otr_api.py).
"""

import argparse
import asyncio
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from playwright.async_api import async_playwright
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("esk_teacher")

BASE_URL = "https://eshikshakosh.bihar.gov.in:8443"
TEACHER_LIST_URL = f"{BASE_URL}/teacher/viewTeacher"
TEACHER_DETAIL_URL = f"{BASE_URL}/teacher/getTeacherDetails"


def current_academic_year() -> str:
    now = datetime.now()
    start_year = now.year if now.month >= 4 else now.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def safe_filename_component(value: str, fallback: str = "School") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in (" ", "-", "_") else " " for ch in str(value or ""))
    cleaned = "_".join(cleaned.split()).strip("._-")
    return cleaned or fallback


def decode_jwt(token: str) -> dict:
    import base64
    try:
        clean = token.replace("Bearer", "").strip()
        parts = clean.split(".")
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception:
        return {}


def _find_school_id(jwt: dict, login_response: dict, uid: str) -> str:
    for key in ("sub", "schoolId", "school_id", "schoolCode", "schoolCodeId", "school"):
        value = jwt.get(key)
        if value not in (None, ""):
            return str(value).strip()
    profile_raw = login_response.get("userProfile", "") if isinstance(login_response, dict) else ""
    try:
        profile = json.loads(profile_raw) if isinstance(profile_raw, str) else profile_raw
    except Exception:
        profile = {}
    if isinstance(profile, dict):
        for key in ("schoolId", "school_id", "schoolCode", "schoolCodeId", "school"):
            value = profile.get(key)
            if value not in (None, ""):
                return str(value).strip()
    return str(uid or "").strip()


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


# ---------------------------------------------------------------------------
# Login (reused from esk_otr_api.py)
# ---------------------------------------------------------------------------

async def login_playwright(uid: str, pwd: str) -> dict:
    captured = {}
    loop = asyncio.get_running_loop()
    previous_exception_handler = loop.get_exception_handler()

    def _capture_asyncio_exception(loop, context):
        exc = context.get("exception")
        if exc is not None:
            captured["async_task_error"] = f"{type(exc).__name__}: {exc}"
        else:
            captured["async_task_error"] = str(context.get("message") or "Background Playwright task failed")
        if previous_exception_handler:
            try:
                previous_exception_handler(loop, context)
            except Exception:
                pass

    loop.set_exception_handler(_capture_asyncio_exception)

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

            direct_token = data.get("token")
            direct_access = data.get("access_token") or data.get("accesstoken")
            if isinstance(direct_token, str) and len(direct_token) > 20:
                captured["token"] = direct_token.replace("Bearer ", "").strip()
            if isinstance(direct_access, str) and len(direct_access) > 20:
                captured["access_token"] = direct_access.replace("Bearer ", "").strip()

            if not captured.get("token"):
                for key, value in find_tokens(data):
                    if key == "token":
                        captured["token"] = value
                        break
            if not captured.get("access_token"):
                for key, value in find_tokens(data):
                    if key in {"access_token", "accesstoken"}:
                        captured["access_token"] = value
                        break

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

        await page.goto("https://eshikshakosh.bihar.gov.in",
                        wait_until="networkidle", timeout=35000)
        await page.click("#radio2")
        await page.wait_for_timeout(400)
        await page.fill("input[formcontrolname='userId']", uid)
        await page.fill("input[formcontrolname='password']", pwd)

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

        try:
            async with page.expect_response(
                lambda resp: "/auth/login" in resp.url.lower(),
                timeout=25000,
            ) as login_response_info:
                await page.click("input.submit__btn")
            login_response = await login_response_info.value
            await on_response(login_response)
        except Exception as exc:
            captured.setdefault("login_error", f"eShikshaKosh login request did not complete: {type(exc).__name__}")

        for _ in range(20):
            if captured.get("token") or captured.get("login_error") or captured.get("login_http_status"):
                break
            await asyncio.sleep(0.25)

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
        try:
            await page.close()
        finally:
            try:
                await context.close()
            finally:
                await browser.close()

    if captured.get("async_task_error") and not captured.get("token") and not captured.get("login_error"):
        captured["login_error"] = "eShikshaKosh background login task failed: " + captured["async_task_error"]
    loop.set_exception_handler(previous_exception_handler)
    return captured


# ---------------------------------------------------------------------------
# Teacher API calls
# ---------------------------------------------------------------------------

def fetch_teacher_list(session, headers, school_id, academic_year, offset=0, limit=100):
    """Fetch teacher list from /teacher/viewTeacher."""
    # Try multiple payload shapes — the portal's teacher endpoint is pickier
    # than the student endpoint and may reject extra/missing fields.
    payloads = [
        {
            "offset": str(offset),
            "limit": str(limit),
            "searchSchoolId": str(school_id),
            "academicYear": str(academic_year),
        },
        {
            "offset": str(offset),
            "limit": str(limit),
            "schoolId": str(school_id),
            "academicYear": str(academic_year),
        },
        {
            "offset": offset,
            "limit": limit,
            "searchSchoolId": str(school_id),
            "academicYear": str(academic_year),
        },
    ]
    for payload in payloads:
        res = session.post(TEACHER_LIST_URL, headers=headers, json=payload,
                           timeout=35, verify=False)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                teachers = data.get("data", data.get("list", data.get("records", [])))
                total = data.get("totalRecord", data.get("total", len(teachers)))
                if teachers:
                    return teachers, total
            elif isinstance(data, list) and data:
                return data, len(data)
        log.warning("viewTeacher HTTP %d: %s", res.status_code, res.text[:200])
    return [], 0


def fetch_teacher_detail(session, headers, teacher_id):
    """Fetch full teacher details from /teacher/getTeacherDetails."""
    try:
        res = session.get(TEACHER_DETAIL_URL, headers=headers,
                         params={"id": teacher_id},
                         timeout=15, verify=False)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                return data.get("data", data)
            return data
    except Exception as e:
        log.warning("getTeacherDetails failed for %s: %s", teacher_id, e)
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main_async(udise, password, academic_year, output, verify_ssl):
    log.info("Logging in as UDISE %s ...", udise)
    captured = await login_playwright(udise, password)
    token = captured.get("token")
    access_token = captured.get("access_token", token)
    if not token:
        detail = str(captured.get("login_error") or "No login token was returned.").strip()
        status = captured.get("login_http_status")
        if status:
            raise RuntimeError(f"{detail} (HTTP {status})")
        raise RuntimeError(detail)

    jwt = decode_jwt(token)
    login_response = captured.get("login_response", {})
    school_id = _find_school_id(jwt, login_response, udise)
    school_enc_id = jwt.get("schoolEncId") or jwt.get("school") or ""

    log.info("School ID: %s | Enc ID: %s", school_id, school_enc_id[:20] if school_enc_id else "N/A")

    headers = build_headers(token, access_token)
    session = build_session(verify_ssl)

    # Fetch teacher list
    log.info("Fetching teacher list from viewTeacher...")
    all_teachers = []
    offset = 0
    limit = 100
    total = None

    while True:
        batch, total = fetch_teacher_list(
            session, headers, school_id, academic_year, offset, limit)
        if not batch:
            break
        all_teachers.extend(batch)
        log.info("Loaded %d teachers (total: %s)", len(all_teachers), total or "?")
        if total and len(all_teachers) >= total:
            break
        if len(batch) < limit:
            break
        offset += limit

    if not all_teachers:
        log.error("No teachers found")
        sys.exit(1)

    school_name = all_teachers[0].get("schoolName") or f"School_{udise}"
    log.info("School: %s | Total: %d", school_name, len(all_teachers))

    # Fetch details in parallel
    log.info("Fetching teacher details (full profile)...")
    teacher_details = {}

    def get_detail(t):
        tid = t.get("teacherLoginCode") or t.get("teacherId") or t.get("id")
        if not tid:
            return tid, {}
        return tid, fetch_teacher_detail(session, headers, tid)

    with ThreadPoolExecutor(max_workers=16) as pool:
        for tid, detail in pool.map(get_detail, all_teachers):
            teacher_details[tid] = detail

    log.info("Details fetched for %d teachers", len(teacher_details))

    # Build records — flatten all available fields
    records = []
    for idx, t in enumerate(all_teachers, 1):
        tid = t.get("teacherLoginCode") or t.get("teacherId") or t.get("id")
        dt = teacher_details.get(tid, {})

        # Merge list + detail data, preferring detail values
        merged = {**t, **dt}

        records.append({
            "S.No.": idx,
            "Teacher Name": str(merged.get("teacherName") or merged.get("name") or "").strip(),
            "Teacher ID": str(merged.get("teacherId") or "--").strip(),
            "Temp Login ID": str(merged.get("teacherLoginCode") or "").strip(),
            "Type of Teacher": str(merged.get("teacherType") or merged.get("type") or "").strip(),
            "Mobile": str(merged.get("mobile") or merged.get("mobileNo") or "").strip(),
            "School Name": str(merged.get("schoolName") or "").strip(),
            "UDISE Code": str(udise).strip(),
            # Additional fields from detail API
            "Father's Name": str(merged.get("fatherName") or "").strip(),
            "Mother's Name": str(merged.get("motherName") or "").strip(),
            "Gender": str(merged.get("gender") or "").strip(),
            "DOB": str(merged.get("dob") or merged.get("dateOfBirth") or "").strip(),
            "Aadhaar Number": str(merged.get("aadhaar") or merged.get("aadhaarNo") or "").strip(),
            "PAN Number": str(merged.get("pan") or merged.get("panNo") or "").strip(),
            "Email": str(merged.get("email") or merged.get("emailId") or "").strip(),
            "Address": str(merged.get("address") or merged.get("permanentAddress") or "").strip(),
            "District": str(merged.get("district") or "").strip(),
            "Block": str(merged.get("block") or "").strip(),
            "Panchayat": str(merged.get("panchayat") or "").strip(),
            "PIN Code": str(merged.get("pinCode") or merged.get("pincode") or "").strip(),
            "Nature of Appointment": str(merged.get("natureOfAppointment") or "").strip(),
            "Category": str(merged.get("category") or merged.get("socialCategory") or "").strip(),
            "Religion": str(merged.get("religion") or "").strip(),
            "Caste": str(merged.get("caste") or "").strip(),
            "Sub Caste": str(merged.get("subCaste") or "").strip(),
            "Qualification": str(merged.get("qualification") or "").strip(),
            "Subject": str(merged.get("subject") or "").strip(),
            "Joining Date": str(merged.get("joiningDate") or merged.get("dateOfJoining") or "").strip(),
            "Confirmation Date": str(merged.get("confirmationDate") or "").strip(),
            "Retirement Date": str(merged.get("retirementDate") or "").strip(),
            "Bank Account No": str(merged.get("bankAccNo") or merged.get("accountNo") or "").strip(),
            "IFSC Code": str(merged.get("IFSC") or merged.get("ifsc") or "").strip().upper(),
            "Bank Name": str(merged.get("bankName") or "").strip(),
            "Branch": str(merged.get("branchName") or "").strip(),
            "GPF Number": str(merged.get("gpfNo") or merged.get("gpfNumber") or "").strip(),
            "PRAN Number": str(merged.get("pranNo") or merged.get("pranNumber") or "").strip(),
            "UAN Number": str(merged.get("uanNo") or merged.get("uanNumber") or "").strip(),
            "Reference Number": str(merged.get("referenceNumber") or "").strip(),
            "Issue Date": str(merged.get("issueDate") or "").strip(),
            "Authority": str(merged.get("authority") or "").strip(),
            "Academic Year": academic_year,
        })

    # Write Excel
    if not output:
        school_part = safe_filename_component(school_name, fallback=str(udise))
        session_part = safe_filename_component(academic_year, fallback="Session")
        output = f"Teacher_Details_{school_part}_{session_part}.xlsx"

    columns = list(records[0].keys())
    wb = Workbook()
    ws = wb.active
    ws.title = "Teachers"

    hfill = PatternFill(start_color="F2F4F7", end_color="F2F4F7", fill_type="solid")
    hfont = Font(name="Calibri", size=10, bold=True, color="1F2937")
    cfont = Font(name="Calibri", size=10, color="111827")
    border = Border(left=Side(style="thin", color="D1D5DB"),
                    right=Side(style="thin", color="D1D5DB"),
                    top=Side(style="thin", color="D1D5DB"),
                    bottom=Side(style="thin", color="D1D5DB"))
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    TEXT_COLS = ["Teacher ID", "Temp Login ID", "Aadhaar Number", "PAN Number",
                 "Mobile", "Bank Account No", "IFSC Code", "GPF Number",
                 "PRAN Number", "UAN Number", "Reference Number", "UDISE Code"]
    text_idx = [columns.index(c) + 1 for c in TEXT_COLS if c in columns]

    CENTER_COLS = ["S.No.", "Gender", "DOB", "Joining Date", "Confirmation Date",
                   "Retirement Date", "Issue Date", "Academic Year"]
    center_idx = [columns.index(c) + 1 for c in CENTER_COLS if c in columns]

    # Write header
    ws.append(columns)
    ws.row_dimensions[1].height = 25
    for cell in ws[1]:
        cell.fill = hfill
        cell.font = hfont
        cell.alignment = center
        cell.border = border

    # Write data
    for ri, rec in enumerate(records, 2):
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

    # Auto-adjust column widths
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[letter].width = min(max(max_len + 4, 13), 45)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    wb.save(output)
    log.info("Saved: %s", output)

    # Summary
    print(f"\n{'='*60}")
    print(f"  Report: {output}")
    print(f"  School: {school_name}")
    print(f"  Total Teachers: {len(records)}")
    print(f"  Details Fetched: {len(teacher_details)}")
    print(f"{'='*60}")


def main():
    import os
    parser = argparse.ArgumentParser(
        description="EshikshaKosh Teacher Report Generator (local)")
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
    args = parser.parse_args()

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
        asyncio.run(main_async(args.udise, args.password, args.year,
                                args.output, args.verify_ssl))
    except RuntimeError as exc:
        log.error("%s", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
