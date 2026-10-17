#!/usr/bin/env python3
"""Unified teacher detail extractor — list + full detail in one script.

Works for any school. Credentials from Bitwarden or CLI.
Output: single Excel with 7 sheets (Teachers, Registration, Education, Professional, Other, Training, Service History).

Usage:
    python3 esk_teacher_unified.py --udise 10160203806 --username <user> --password <pass>
    python3 esk_teacher_unified.py --school Tetahali
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "https://eshikshakosh.bihar.gov.in"
API = "https://eshikshakosh.bihar.gov.in:8443"
PAGE_SIZE = "100"
AUTH_HEADER_NAMES = {"accept", "content-type", "authorization", "accesstoken", "authtoken", "authaccess"}

DETAIL_ENDPOINTS = [
    ("registrationInfo", "/teacher/registrationInfo", "encId"),
    ("teacherDetails", "/teacher/getTeacherDetails", "teacherId"),
    ("educationInfo", "/teacher/viewTeacherEducationInfo", "encId"),
    ("professionalInfo", "/teacher/viewTeacherProfessionalInfo", "encId"),
    ("otherInfo", "/teacher/viewTeacherOtherInfo", "encId"),
    ("trainingInfo", "/teacher/viewTeacherTrainingInfo", "encId"),
    ("serviceInfo", "/teacher/getExistingServiceInfo", "teacherEncryptedId"),
]

GENDER_MAP = {"1": "Male", "2": "Female"}


def require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


def slugify(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", (text or "").strip()).strip("_") or "Unknown_School"


def rows_of(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("serviceInfo", "educationInfo", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for sub in ("data", "list", "records", "result"):
                    if isinstance(value.get(sub), list):
                        return value[sub]
    return []


def unpack(response_json):
    if not isinstance(response_json, dict):
        return [], 0
    rows = response_json.get("data", [])
    total = response_json.get("totalRecord", 0)
    if isinstance(rows, dict):
        total = rows.get("totalRecord", total)
        rows = rows.get("data", [])
    if not isinstance(rows, list):
        rows = []
    try:
        total = int(total or len(rows))
    except (ValueError, TypeError):
        total = len(rows)
    return rows, total


def ask_school():
    """Ask which school's data is needed. Never assume."""
    print("\nKaunsi school ka data chahiye?")
    print("  1. UMV Tetahali")
    print("  2. UMV Sahaspur")
    print("  3. Doosri school")
    choice = input("\nNumber batao (1/2/3): ").strip()
    if choice == "1":
        return "10160203806", "Tetahali"
    elif choice == "2":
        return "10130106304", "Sahaspur"
    elif choice == "3":
        udise = input("School ka UDISE code batao (11 digits): ").strip()
        return udise, f"UDISE_{udise}"
    else:
        print("Galat choice, Tetahali select kar raha hoon")
        return "10160203806", "Tetahali"


def ask_credentials(school_name):
    """Ask for credentials if not in Bitwarden. Never assume."""
    print(f"\n{school_name} ke liye login chahiye")
    print("  1. Bitwarden se (save ho toh)")
    print("  2. Khud likho")
    choice = input("\nNumber batao (1/2): ").strip()
    if choice == "1":
        return None, None
    else:
        uid = input("Username: ").strip()
        pwd = input("Password: ").strip()
        return uid, pwd


def ask_detail_level():
    """Ask how much detail is needed."""
    print("\nKitna detail chahiye?")
    print("  1. Sirf list — naam, mobile, address (jaldi hai)")
    print("  2. Full detail — education, service history, training sab (thoda time)")
    choice = input("\nNumber batao (1/2): ").strip()
    return choice == "2"


async def main():
    # Ask which school
    target_udise, school_name = ask_school()
    
    # Ask for credentials
    uid, pwd = ask_credentials(school_name)

    # If not provided manually, require from env/Bitwarden
    if not uid:
        uid = require_env("ESHIKSHAKOSH_USERNAME")
    if not pwd:
        pwd = require_env("ESHIKSHAKOSH_PASSWORD")

    # Ask detail level
    want_full_detail = ask_detail_level()
    
    out_dir = Path(os.environ.get("ESHIKSHAKOSH_OUT") or (Path.home() / "exports"))
    limit = os.environ.get("ESHIKSHAKOSH_DETAIL_LIMIT")

    print(f"TARGET_UDISE={target_udise}")
    print(f"SCHOOL={school_name}")

    auth = {}
    teachers, total = [], 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        async def capture_auth(route):
            req = route.request
            try:
                payload = json.loads(req.post_data or "{}")
            except (json.JSONDecodeError, TypeError):
                await route.continue_()
                return
            payload["offset"] = "0"
            payload["limit"] = PAGE_SIZE
            payload["schoolUdiseCode"] = target_udise
            hdrs = await req.all_headers()
            auth.update({k.lower(): v for k, v in hdrs.items() if k.lower() in AUTH_HEADER_NAMES})
            await route.continue_(post_data=json.dumps(payload))

        await page.route("**/teacher/viewTeacher", capture_auth)

        try:
            # Login
            await page.goto(BASE, wait_until="networkidle", timeout=90000)
            await page.wait_for_timeout(3000)
            if await page.locator("#radio2").count():
                await page.click("#radio2")
                await page.wait_for_timeout(300)
            await page.locator("input[formcontrolname='userId']").wait_for(state="visible", timeout=15000)
            await page.fill("input[formcontrolname='userId']", uid)
            await page.fill("input[formcontrolname='password']", pwd)

            captcha = await page.inner_text(".capcha__head")
            m = re.search(r"(\d+)\s*([+\-*])\s*(\d+)", captcha)
            if not m:
                raise RuntimeError("Captcha not recognized")
            a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
            await page.fill("input[placeholder='Enter User Captcha']", str(a + b if op == "+" else a - b if op == "-" else a * b))

            async with page.expect_response(lambda r: "/auth/login" in r.url.lower(), timeout=35000) as login_info:
                await page.click("input.submit__btn")
            login_resp = await login_info.value
            print(f"LOGIN_HTTP={login_resp.status}")
            if login_resp.status != 200:
                raise RuntimeError(f"Login failed: HTTP {login_resp.status}")
            login_json = await login_resp.json()
            if login_json.get("success") is False:
                raise RuntimeError("Login rejected")
            await page.wait_for_timeout(1200)

            # Get teacher list
            await page.goto(f"{BASE}/Application/teacher/registration/viewTeacher", wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)
            search = page.locator("button:has-text('Search')")
            if not await search.count():
                raise RuntimeError("Search button not found")
            async with page.expect_response(lambda r: "/teacher/viewTeacher" in r.url and r.request.method == "POST", timeout=45000) as teacher_info:
                await search.first.click()
            first_json = await (await teacher_info.value).json()
            teachers, total = unpack(first_json)
            if not teachers:
                raise RuntimeError("No teachers found")
            if not auth:
                raise RuntimeError("Could not capture auth context")

            # Pagination
            while len(teachers) < total:
                offset = len(teachers)
                payload = {"offset": str(offset), "limit": PAGE_SIZE, "schoolUdiseCode": target_udise}
                res = await page.evaluate("""async ({url, payload, headers}) => {
                    const r = await fetch(url, {method:'POST', headers, body:JSON.stringify(payload)});
                    let body; try { body = await r.json(); } catch (_) { body = null; }
                    return {status:r.status, body};
                }""", {"url": f"{API}/teacher/viewTeacher", "payload": payload, "headers": auth})
                if res.get("status") != 200:
                    raise RuntimeError(f"Pagination failed: HTTP {res.get('status')}")
                nxt, nxt_total = unpack(res.get("body"))
                if not nxt:
                    raise RuntimeError(f"Pagination stopped at {len(teachers)} of {total}")
                teachers.extend(nxt)
                total = max(total, nxt_total)

            # Scope validation
            wrong = [t for t in teachers if str(t.get("schoolUdiseCode") or "").strip() != target_udise]
            if wrong:
                raise RuntimeError(f"Scope validation failed: {len(wrong)} rows don't match UDISE {target_udise}")

            if limit:
                teachers = teachers[: int(limit)]
                print(f"LIMIT_APPLIED={len(teachers)}")

            print(f"TEACHERS_FOUND={len(teachers)}")

            # Fetch details for each teacher (only if full detail requested)
            async def call(path, payload):
                res = await page.evaluate("""async ({url, payload, headers}) => {
                    const r = await fetch(url, {method:'POST', headers, body:JSON.stringify(payload)});
                    let body; try { body = await r.json(); } catch (_) { body = null; }
                    return {status:r.status, body};
                }""", {"url": API + path, "payload": payload, "headers": auth})
                return res

            details = []
            if want_full_detail:
                print("Detail fetch shuru ho raha hai...")
                for idx, teacher in enumerate(teachers, 1):
                    enc = str(teacher.get("encId") or "").strip()
                    tId = str(teacher.get("tId") or "").strip()
                    name = teacher.get("teacherName", "")

                    if not enc:
                        print(f"  [{idx}/{len(teachers)}] {name} — encId nahi hai, skip")
                        details.append({"teacher": teacher, "sections": {}})
                        continue

                    sections = {}
                    for section_name, path, key in DETAIL_ENDPOINTS:
                        try:
                            payload = {key: enc if key == "encId" else tId}
                            if key == "teacherEncryptedId":
                                payload = {key: enc}
                            res = await call(path, payload)
                            body = res.get("body")
                            if res.get("status") != 200:
                                sections[section_name] = {"error": f"HTTP {res.get('status')}"}
                            else:
                                sections[section_name] = body if isinstance(body, dict) else {"data": body}
                        except Exception as exc:
                            sections[section_name] = {"error": f"{type(exc).__name__}: {exc}"}

                    details.append({"teacher": teacher, "sections": sections})
                    print(f"  [{idx}/{len(teachers)}] {name} — ho gaya")
                    await page.wait_for_timeout(400)
            else:
                print("Sirf list ban rahi hai...")
                for teacher in teachers:
                    details.append({"teacher": teacher, "sections": {}})

        finally:
            await context.close()
            await browser.close()

    # Export to Excel
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    school_slug = slugify(str(teachers[0].get("schoolName") or "")) if teachers else slugify(target_udise)
    output = out_dir / f"Teacher_Details_{school_slug}_{timestamp}.xlsx"
    write_workbook(teachers, details, str(output))

    os.chmod(output, 0o600)
    print(f"TEACHERS={len(teachers)}")
    print(f"WORKBOOK={output}")
    print("SOURCE=authenticated Playwright browser session; read-only")


def write_workbook(teachers, details, filename):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()

    # Formatting
    header_fill = PatternFill(start_color="F2F4F7", end_color="F2F4F7", fill_type="solid")
    header_font = Font(bold=True, color="1F2937", size=10)
    thin_border = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )

    # Sheet 1: Teachers list
    ws = wb.active
    ws.title = "Teachers"
    headers = ["S.No.", "Temp Login ID", "Teacher Name", "Gender", "Marital Status",
               "DOB", "Teacher Title", "Nature of Appointment", "Service Joining",
               "Joining Current School", "Class Category", "Appointed Subject",
               "Mobile", "Email", "PAN", "HRMS ID", "PRAN", "GPF", "UAN",
               "Aadhaar", "Social Category", "Domicile No", "Mother", "Father",
               "Current Address", "Permanent Address", "School Name", "UDISE"]
    ws.append(headers)
    for c in ws[1]:
        c.fill = header_fill
        c.font = header_font
        c.border = thin_border

    for i, t in enumerate(teachers, 1):
        gender = t.get("gender", "")
        if str(gender).strip() in GENDER_MAP:
            gender = GENDER_MAP[str(gender).strip()]
        ws.append([
            i, t.get("teacherLoginCode"), t.get("teacherName"), gender,
            t.get("maritalStatus"), t.get("DOB"), t.get("teacherTitle"),
            t.get("natureOfAppointmt"), t.get("serviceJoiningDt"),
            t.get("joiningCurrentSchoolDt"), t.get("classCategory"),
            t.get("appointedSubject"), t.get("mobile"), t.get("teacherEmail"),
            t.get("panNo"), t.get("employeeCode"), t.get("pranNo"),
            t.get("gpfNo"), t.get("uanNo"), t.get("aadhaarNo"),
            t.get("socialCategory"), t.get("pDomicileNumber"),
            t.get("motherName"), t.get("fatherName"),
            t.get("cVillage", ""), t.get("pVillage", ""),
            t.get("schoolName"), t.get("schoolUdiseCode"),
        ])

    # Sheet 2: Registration Info
    ws = wb.create_sheet("Registration Info")
    reg_keys = ["tId", "teacherName", "prefix", "firstName", "middleName", "lastName",
                "gender", "DOB", "socialCategory", "religion", "mobile", "aadhaarNo",
                "teacherTitle", "natureOfAppointmt", "serviceJoiningDt", "appointedSubject",
                "classCategory", "appointmentType", "appointingAuth",
                "joiningCurrentSchoolDt", "bpscRollNo", "employeeCode", "panNo",
                "gpfNo", "pranNo", "uanNo", "fatherName", "motherName", "spouseName",
                "maritalStatus", "teacherEmail", "bloodGroup", "disabilityStatus",
                "awardStatus", "pDomicileNumber", "pDomicile", "schoolUdiseCode",
                "pHouseName", "pStreet", "pPostOffice", "pPanchayat", "pVillage",
                "pPIN", "pDistrictId", "pBlockId", "pStateName",
                "cHouseName", "cStreet", "cPostOffice", "cPanchayat", "cVillage",
                "cPIN", "cDistrictId", "cBlockId", "cStateName"]
    ws.append(reg_keys)
    for c in ws[1]:
        c.fill = header_fill
        c.font = header_font
        c.border = thin_border
    for item in details:
        sec = (item.get("sections") or {}).get("registrationInfo") or {}
        data = sec.get("data") if isinstance(sec, dict) else None
        if not isinstance(data, dict):
            data = {}
        ws.append([data.get(k, "") for k in reg_keys])

    # Sheets 3-7: Repeating sections
    for sheet_name, section_name in [
        ("Education", "educationInfo"),
        ("Professional", "professionalInfo"),
        ("Other Info", "otherInfo"),
        ("Training", "trainingInfo"),
        ("Service History", "serviceInfo"),
    ]:
        ws = wb.create_sheet(sheet_name)
        written = 0
        for item in details:
            teacher = item.get("teacher") or {}
            sec = (item.get("sections") or {}).get(section_name) or {}
            if isinstance(sec, dict) and sec.get("error"):
                continue
            records = rows_of(sec)
            if not records:
                continue
            keys = list(records[0].keys()) if isinstance(records[0], dict) else []
            if written == 0:
                ws.append(["Teacher ID", "Teacher Name"] + keys)
                for c in ws[1]:
                    c.fill = header_fill
                    c.font = header_font
                    c.border = thin_border
            for rec in records:
                row_data = [teacher.get("tId"), teacher.get("teacherName")]
                for k in keys:
                    v = rec.get(k, "") if isinstance(rec, dict) else ""
                    if isinstance(v, (list, dict)):
                        v = json.dumps(v, ensure_ascii=False)
                    row_data.append(v)
                ws.append(row_data)
                written += 1
        if written == 0:
            ws.append(["Teacher ID", "Teacher Name", "Status"])
            ws.append(["", "", "No records for this school"])

    # Auto-size columns
    for ws in wb.worksheets:
        for col in range(1, min(ws.max_column, 80) + 1):
            width = len(str(ws.cell(row=1, column=col).value or ""))
            for row in range(2, min(ws.max_row, 60) + 1):
                val = ws.cell(row=row, column=col).value
                width = max(width, len(str(val)) if val is not None else 0)
            ws.column_dimensions[get_column_letter(col)].width = min(width + 2, 40)
        ws.freeze_panes = "A2"

    wb.save(filename)


if __name__ == "__main__":
    asyncio.run(main())
