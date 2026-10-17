#!/usr/bin/env python3
"""Extract all teacher details from e-ShikshaKosh using intercepted API payload pattern."""
import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from playwright.async_api import async_playwright
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("extract")

BASE_URL = "https://eshikshakosh.bihar.gov.in:8443"
TEACHER_LIST_URL = f"{BASE_URL}/teacher/viewTeacher"


def build_session():
    s = requests.Session()
    s.verify = False
    retries = Retry(total=4, backoff_factor=0.6,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["POST", "GET"])
    adapter = HTTPAdapter(max_retries=retries, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def build_headers(token, access_token):
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


async def login_and_capture_encrypted_ids(uid, pwd):
    """Login and capture encrypted schoolId + userId from teacherCount API call."""
    captured = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        # Capture teacherCount API call to get encrypted IDs
        async def on_response(response):
            if "/teacher/teacherCount" in response.url:
                try:
                    req = response.request
                    body = req.post_data
                    if body:
                        data = json.loads(body)
                        captured["schoolId"] = data.get("school", "")
                        captured["userId"] = data.get("userId", "")
                        captured["userRole"] = data.get("userRole", "")
                        captured["encLoginUserType"] = data.get("encLoginUserType", "")
                        captured["district"] = data.get("district", "")
                        captured["block"] = data.get("block", "")
                        captured["cluster"] = data.get("cluster", "")
                        captured["schoolCategory"] = data.get("schoolCategory", "")
                        captured["management"] = data.get("management", "")
                        captured["udiseCode"] = data.get("udiseCode", "")
                        captured["designation"] = data.get("designation", "")
                        captured["minClass"] = data.get("minClass", "")
                        captured["maxClass"] = data.get("maxClass", "")
                        captured["isPrivateSchool"] = data.get("isPrivateSchool", "")
                        captured["isUrduSchool"] = data.get("isUrduSchool", "")
                        captured["subDivision"] = data.get("subDivision", "")
                        captured["loginUserTypeId"] = data.get("loginUserTypeId", "")
                        captured["userRoleId"] = data.get("userRoleId", "")
                        captured["userName"] = data.get("userName", "")
                        captured["loginId"] = data.get("loginId", "")
                        captured["loginUserType"] = data.get("loginUserType", "")
                        captured["userType"] = data.get("userType", "")
                        captured["mobileMask"] = data.get("mobileMask", "")
                        captured["email"] = data.get("email", "")
                        captured["ENSMSOTP_AEBYS"] = data.get("ENSMSOTP_AEBYS", "")
                        captured["passwordPoliciesRemainingDays"] = data.get("passwordPoliciesRemainingDays", "")
                        captured["designationId"] = data.get("designationId", "")
                        log.info(f"Captured encrypted schoolId: {captured['schoolId'][:30]}...")
                        log.info(f"Captured encrypted userId: {captured['userId'][:30]}...")
                except Exception as e:
                    log.warning(f"Failed to parse teacherCount body: {e}")

        page.on("response", on_response)

        # Login
        await page.goto("https://eshikshakosh.bihar.gov.in",
                        wait_until="networkidle", timeout=35000)
        await page.click("#radio2")
        await page.wait_for_timeout(400)

        await page.fill("input[formcontrolname='userId']", uid)
        await page.fill("input[formcontrolname='password']", pwd)

        captcha_text = await page.inner_text(".capcha__head")
        match = re.search(r"(\d+)\s*([+\-*])\s*(\d+)", captcha_text)
        if match:
            left, op, right = int(match.group(1)), match.group(2), int(match.group(3))
            answer = left + right if op == "+" else left - right if op == "-" else left * right
            await page.fill("input[placeholder='Enter User Captcha']", str(answer))
            log.info(f"Captcha solved: {left}{op}{right}={answer}")

        # Capture login response for tokens
        async with page.expect_response(
            lambda resp: "/auth/login" in resp.url.lower(),
            timeout=25000,
        ) as login_info:
            await page.click("input.submit__btn")

        login_resp = await login_info.value
        login_data = await login_resp.json()
        log.info(f"Login HTTP {login_resp.status}")

        # Extract tokens
        direct_token = login_data.get("token", "")
        direct_access = login_data.get("access_token") or login_data.get("accesstoken", "")
        if isinstance(direct_token, str) and len(direct_token) > 20:
            captured["token"] = direct_token.replace("Bearer ", "").strip()
        if isinstance(direct_access, str) and len(direct_access) > 20:
            captured["access_token"] = direct_access.replace("Bearer ", "").strip()

        # Fallback: sessionStorage
        if not captured.get("token"):
            try:
                storage = await page.evaluate("Object.fromEntries(Object.entries(sessionStorage))")
                jwt_token = str(storage.get("jwtToken") or "").strip()
                access_token = str(storage.get("access_token") or "").strip()
                if jwt_token:
                    captured["token"] = jwt_token
                    captured["access_token"] = access_token or jwt_token
            except Exception:
                pass

        # Navigate to viewTeacher page to trigger teacherCount API
        await page.goto(
            "https://eshikshakosh.bihar.gov.in/Application/teacher/registration/viewTeacher",
            wait_until="networkidle", timeout=35000,
        )
        await page.wait_for_timeout(5000)

        # Click Search to trigger viewTeacher API too
        try:
            search_btn = page.locator("button:has-text('Search'), button:has-text('search')")
            if await search_btn.count() > 0:
                await search_btn.first.click()
                log.info("Clicked Search button")
                await page.wait_for_timeout(3000)
        except Exception:
            pass

        # Extract dropdown mappings from viewTeacher page (dropdowns are here)
        # No need to navigate away — viewTeacher page has the dropdowns

        # Extract dropdown mappings from teacher page (with labels)
        try:
            mappings = await page.evaluate("""() => {
                const result = {};
                const selects = document.querySelectorAll('select');
                selects.forEach((sel, idx) => {
                    // Find associated label
                    let label = '';
                    const id = sel.id;
                    if (id) {
                        const labelEl = document.querySelector("label[for='" + id + "']");
                        if (labelEl) label = labelEl.textContent.trim();
                    }
                    // Check previous sibling
                    if (!label) {
                        const prev = sel.previousElementSibling;
                        if (prev) label = prev.textContent.trim().substring(0, 80);
                    }
                    // Check parent
                    if (!label) {
                        const parent = sel.parentElement;
                        if (parent) {
                            const parentText = parent.textContent.trim();
                            // Get text before the select
                            const selectIdx = parentText.indexOf(sel.options[0]?.text || '');
                            if (selectIdx > 0) {
                                label = parentText.substring(0, selectIdx).trim().substring(0, 80);
                            }
                        }
                    }
                    const name = sel.name || sel.id || label || `select_${idx}`;
                    const options = Array.from(sel.options).map(o => ({
                        value: o.value,
                        text: o.text.trim(),
                    })).filter(o => o.value !== '' && o.text !== '');
                    if (options.length > 0) {
                        result[name] = options;
                    }
                });
                return result;
            }""")
            if mappings:
                captured["dropdown_mappings"] = mappings
                log.info(f"Extracted {len(mappings)} dropdown mappings")
                # Print mappings with all options for verification
                for name, opts in mappings.items():
                    log.info(f"  {name}: {len(opts)} options — {[(o['value'], o['text']) for o in opts[:5]]}")
        except Exception as e:
            log.warning(f"Dropdown mapping extraction failed: {e}")

        # Also capture viewTeacher payload for reference
        await page.close()
        await context.close()
        await browser.close()

    return captured


async def extract_dropdown_mappings(uid, pwd):
    """Extract dropdown option mappings from teacher registration page."""
    from playwright.async_api import async_playwright

    parts = uid.split("_")
    school_part = "_".join(parts[1:-2])
    udise_map = {
        "UMV_TETAHALI": "10160203806",
        "UMV_SAHASPUR": "10130106304",
    }
    school_id = udise_map.get(school_part, "")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto("https://eshikshakosh.bihar.gov.in", wait_until="networkidle", timeout=90000)
            await page.wait_for_timeout(5000)

            udise_input = page.locator("input[placeholder='11-Digit UDISE Code']")
            await udise_input.wait_for(state="visible", timeout=30000)
            await udise_input.fill(school_id)
            await page.fill("input[placeholder='Password']", pwd)
            await page.wait_for_timeout(500)

            await page.evaluate("""() => {
                const caps = document.querySelectorAll('.badge');
                caps.forEach(c => { if (c.offsetWidth > 0 && c.offsetHeight > 0) c.click(); });
            }""")
            await page.wait_for_timeout(500)

            await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const loginBtn = btns.find(b => b.textContent.trim().toLowerCase().includes('login'));
                if (loginBtn) loginBtn.click();
            }""")

            try:
                await page.wait_for_response(lambda r: "/auth/login" in r.url, timeout=60000)
            except Exception:
                pass
            await page.wait_for_timeout(2000)

            await page.goto(
                f"https://eshikshakosh.bihar.gov.in:8443/school/teacher-registration?schoolId={school_id}&academicYear=2026-2027",
                wait_until="networkidle",
                timeout=60000
            )
            await page.wait_for_timeout(3000)

            await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const searchBtn = btns.find(b => b.textContent.trim().toLowerCase().includes('search'));
                if (searchBtn) searchBtn.click();
            }""")
            await page.wait_for_timeout(3000)

            mappings = await page.evaluate("""() => {
                const result = {};
                const selects = document.querySelectorAll('select');
                selects.forEach((sel, idx) => {
                    const name = sel.name || sel.id || `select_${idx}`;
                    const options = Array.from(sel.options).map(o => ({
                        value: o.value,
                        text: o.text.trim(),
                    })).filter(o => o.value !== '' && o.text !== '');
                    if (options.length > 0) {
                        result[name] = options;
                    }
                });
                return result;
            }""")

            await browser.close()
            return mappings

        except Exception as e:
            print(f"  ⚠️ Dropdown extraction failed: {e}")
            await browser.close()
            return {}


def fetch_all_teachers(session, headers, captured, academic_year="2026-27"):
    """Fetch all teachers using the exact payload structure from browser."""
    # Build the exact payload the browser sends
    payload = {
        "offset": "0",
        "limit": "100",
        "serviceType": "Search",
        "searchDistrictId": captured.get("district", 16),
        "searchBlockId": captured.get("block", 219),
        "searchClusterId": captured.get("cluster", 2471),
        "searchSchoolId": 42645,
        "searchTeacherTitle": "",
        "searchNatureOfAppointmt": "",
        "searchTeacherId": "",
        "schoolUdiseCode": "",
        "searchTeacherTempLoginId": "",
        "searchTeacherName": "",
        "searchStatusWise": "",
        "searchVerification": "",
        "schoolId": captured.get("schoolId", ""),
        "userId": captured.get("userId", ""),
        "loginUserTypeId": captured.get("loginUserTypeId", 2),
        "district": captured.get("district", 16),
        "block": captured.get("block", 219),
        "cluster": captured.get("cluster", 2471),
        "searchDeputationWise": "1",
        "searchTeacherSubTitle": "",
        "searchSchoolManagement": "",
        "searchSchoolCategory": "",
        "scDistrictName": "",
        "scBlockName": "",
        "scClusterName": "",
        "scSchoolName": "",
        "scAppointmtName": "",
        "scTeacherTypeName": "",
        "scManagementName": "",
        "scStatusName": "",
        "scDeputName": "",
        "scTeacherSubTypeName": "",
    }

    all_teachers = []
    offset = 0
    limit = 100

    while True:
        payload["offset"] = str(offset)
        payload["limit"] = str(limit)

        log.info(f"Fetching teachers offset={offset} limit={limit}")
        res = session.post(TEACHER_LIST_URL, headers=headers, json=payload, timeout=35)

        if res.status_code != 200:
            log.error(f"HTTP {res.status_code}: {res.text[:300]}")
            break

        data = res.json()
        teachers = data.get("data", [])
        total = data.get("totalRecord", 0)

        if not teachers:
            break

        all_teachers.extend(teachers)
        log.info(f"Got {len(teachers)} teachers (total: {len(all_teachers)}/{total})")

        if len(all_teachers) >= total or len(teachers) < limit:
            break

        offset += limit

    return all_teachers


def export_to_excel(teachers, filename, value_mappings=None):
    """Export teacher data to Excel with all fields."""
    try:
        import openpyxl
    except ImportError:
        os.system("pip install openpyxl -q")
        import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Teachers"

    if not teachers:
        log.warning("No teachers to export")
        wb.save(filename)
        return

    # Column order per user specification:
    # Serial, ID, Name, Gender, DOB, Type, Joining, Mobile, Email, PAN, PRAN, GPF, UAN, Aadhaar,
    # Social Category, Mother, Father, Marital Status, Nature of Appointment,
    # Address, School, Domicile Number (last)
    priority_fields = [
        "slNo", "teacherLoginCode", "teacherName", "gender", "maritalStatus", "DOB", "teacherTitle", "natureOfAppointmt", "serviceJoiningDt", "joiningCurrentSchoolDt", "classCategory", "appointedSubject",
        "mobile", "teacherEmail", "panNo", "employeeCode", "pranNo", "gpfNo", "uanNo", "aadhaarNo", "socialCategory", "pDomicileNumber",
        "motherName", "fatherName",
        # Address (combined into single cells)
        "_currentAddress", "_permanentAddress",
        # School
        "schoolName", "schoolUdiseCode",
    ]

    # Get all unique keys from all teachers
    all_keys = set()
    for t in teachers:
        all_keys.update(t.keys())

    # Final output format: 28 curated columns (user-specified order)
    all_columns = [
        "Sr No", "teacherLoginCode", "teacherName", "gender", "maritalStatus", "DOB",
        "teacherTitle", "natureOfAppointmt", "serviceJoiningDt", "joiningCurrentSchoolDt",
        "classCategory", "appointedSubject", "mobile", "teacherEmail", "panNo",
        "employeeCode", "pranNo", "gpfNo", "uanNo", "aadhaarNo", "socialCategory",
        "pDomicileNumber", "motherName", "fatherName", "_currentAddress", "_permanentAddress",
        "schoolName", "schoolUdiseCode"
    ]

    # Meaningful header mapping
    HEADER_MAP = {
        "tId": "Teacher ID",
        "teacherLoginCode": "Temp Login ID",
        "teacherCode": "Teacher Code",
        "teacherName": "Teacher Name",
        "prefix": "Prefix",
        "firstName": "First Name",
        "middleName": "Middle Name",
        "lastName": "Last Name",
        "gender": "Gender",
        "teacherType": "Teacher Type",
        "teacherTitle": "Teacher Title",
        "natureOfAppointmt": "Nature of Appointment",
        "mobile": "Mobile",
        "teacherEmail": "Email",
        "DOB": "Date of Birth",
        "maritalStatus": "Marital Status",
        "socialCategory": "Social Category",
        "religion": "Religion",
        "disabilityStatus": "Disability Status",
        "aadhaarNo": "Aadhaar Number",
        "panNo": "PAN Number",
        "gpfNo": "GPF Number",
        "pranNo": "PRAN Number",
        "uanNo": "UAN Number",
        "employeeCode": "Employee Code",
        "fatherName": "Father Name",
        "motherName": "Mother Name",
        "serviceJoiningDt": "Service Joining Date",
        "joiningCurrentSchoolDt": "Joining Current School Date",
        "schoolName": "School Name",
        "schoolUdiseCode": "School UDISE Code",
        "clusterName": "Cluster Name",
        "districtCode": "District Code",
        "districtName": "District Name",
        "blockCode": "Block Code",
        "blockName": "Block Name",
        "clusterCode": "Cluster Code",
        "appointingAuth": "Appointing Authority",
        "appointmentType": "Appointment Type",
        "classCategory": "Class Category",
        "appointedSubject": "Appointed Subject",
        "jfDistrictCode": "JF District Code",
        "pHouseName": "Permanent House Name",
        "pStreet": "Permanent Street",
        "pPanchayat": "Permanent Panchayat",
        "pVillage": "Permanent Village",
        "pPIN": "Permanent PIN",
        "pState": "Permanent State",
        "pDistrictId": "Permanent District ID",
        "pBlockId": "Permanent Block ID",
        "pPostOffice": "Permanent Post Office",
        "pDistrictOther": "Permanent District Other",
        "pBlockOther": "Permanent Block Other",
        "pPanchayatOther": "Permanent Panchayat Other",
        "pDomicile": "Permanent Domicile",
        "pDomicileNumber": "Permanent Domicile Number",
        "cHouseName": "Current House Name",
        "cStreet": "Current Street",
        "cPanchayat": "Current Panchayat",
        "cVillage": "Current Village",
        "cPIN": "Current PIN",
        "cState": "Current State",
        "cDistrictId": "Current District ID",
        "cBlockId": "Current Block ID",
        "cPostOffice": "Current Post Office",
        "cDistrictOther": "Current District Other",
        "cBlockOther": "Current Block Other",
        "cPanchayatOther": "Current Panchayat Other",
        "isTeacherUpdatePermanentAddress": "Update Permanent Address",
        "isPAddressCorrect": "Is P Address Correct",
        "status": "Status",
        "lastServiceStatus": "Last Service Status",
        "profileStatus": "Profile Status",
        "verificationStatus": "Verification Status",
        "verificationRemarks": "Verification Remarks",
        "verificationDate": "Verification Date",
        "salaryInfoStatus": "Salary Info Status",
        "serviceInfoStatus": "Service Info Status",
        "pendingAt": "Pending At",
        "changeRequestStatus": "Change Request Status",
        "changeRequestStatusRemarks": "Change Request Remarks",
        "verifiedDataStatus": "Verified Data Status",
        "editProfileStatus": "Edit Profile Status",
        "scModificationReqStatus": "SC Modification Request Status",
        "schRevertsts": "School Revert Status",
        "createdOn": "Created On",
        "createdBy": "Created By",
        "isPrivateTeacher": "Is Private Teacher",
        "updateDeputationStatus": "Update Deputation Status",
        "beoVerifiedOn": "BEO Verified On",
        "niyojitTchCretedUpdatedDPO": "Niyojit Teacher Created Updated DPO",
        "niyojitTchCretedUpdatedDpoOn": "Niyojit Teacher Created Updated DPO On",
        "ccVerifiedSts": "CC Verified Status",
        "ccVerifiedOn": "CC Verified On",
        "encId": "Encrypted ID",
        "schoolId": "School ID (Encrypted)",
        "scDistrictId": "SC District ID",
        "scBlockId": "SC Block ID",
        "pranGpfUanEditStatus": "PRAN GPF UAN Edit Status",
        "profileColor": "Profile Color",
        "salaryInfoColor": "Salary Info Color",
        "serviceInfoColor": "Service Info Color",
        "educationInfoStatus": "Education Info Status",
        "educationInfoColor": "Education Info Color",
        "subjectCategoryUpdateStatus": "Subject Category Update Status",
        "resetAddressUpdate": "Reset Address Update",
        "slNo": "Serial No",
        "awardStatus": "Award Status",
        "scClusterId": "SC Cluster ID",
        "districtId": "District ID",
        "_permanentAddress": "Permanent Address",
        "_currentAddress": "Current Address",
    }

    def header_for(key):
        return HEADER_MAP.get(key, key)

    # Write header with meaningful names
    for col_idx, key in enumerate(all_columns, 1):
        ws.cell(row=1, column=col_idx, value=header_for(key))

    # Build mappings ONLY from explicitly identified portal dropdowns.
    # Do not infer mappings from select_N positions or hard-coded code tables: those
    # produced incorrect labels (notably social category, class category and subject).
    field_value_map = {}
    if value_mappings:
        dropdown_to_field = {
            "searchNatureOfAppointmt": "natureOfAppointmt",
            "select_5": "maritalStatus",
            "select_6": "pState",
            "select_7": "pDistrictId",
            "select_10": "cState",
            "select_11": "cDistrictId",
        }
        for dropdown_name, options in value_mappings.items():
            field_name = dropdown_to_field.get(dropdown_name)
            if not field_name:
                continue
            value_map = {}
            for opt in options:
                raw_value = str(opt.get("value", "")).strip()
                label = str(opt.get("text", "")).strip()
                if raw_value and label:
                    value_map[raw_value] = label
            if value_map:
                normalized = field_name.lower().replace("_", "").replace("-", "").replace(" ", "")
                field_value_map[normalized] = value_map
                field_value_map[field_name] = value_map

    # Gender code mapping: 1 → Male, 2 → Female
    GENDER_MAP = {"1": "Male", "2": "Female"}

    # Address field groups for combining into single cells
    PERMANENT_ADDRESS_FIELDS = [
        "pHouseName", "pStreet", "pPanchayat", "pVillage", "pPIN",
        "pState", "pDistrictId", "pBlockId", "pPostOffice",
        "pDistrictOther", "pBlockOther", "pPanchayatOther",
    ]
    CURRENT_ADDRESS_FIELDS = [
        "cHouseName", "cStreet", "cPanchayat", "cVillage", "cPIN",
        "cState", "cDistrictId", "cBlockId", "cPostOffice",
        "cDistrictOther", "cBlockOther", "cPanchayatOther",
    ]

    ADDRESS_LABELS = {
        "pHouseName": "House", "pStreet": "Street", "pPanchayat": "Panchayat",
        "pVillage": "Village", "pPIN": "PIN", "pState": "State",
        "pDistrictId": "District", "pBlockId": "Block", "pPostOffice": "Post Office",
        "pDistrictOther": "District Other", "pBlockOther": "Block Other",
        "pPanchayatOther": "Panchayat Other",
        "cHouseName": "House", "cStreet": "Street", "cPanchayat": "Panchayat",
        "cVillage": "Village", "cPIN": "PIN", "cState": "State",
        "cDistrictId": "District", "cBlockId": "Block", "cPostOffice": "Post Office",
        "cDistrictOther": "District Other", "cBlockOther": "Block Other",
        "cPanchayatOther": "Panchayat Other",
    }

    def combine_address(teacher, fields):
        """Combine address fields into a compact labeled format."""
        parts = []
        for f in fields:
            v = teacher.get(f, "")
            if v is not None and str(v).strip() != "":
                label = ADDRESS_LABELS.get(f, f)
                parts.append(f"{label}: {str(v).strip()}")
        return ", ".join(parts) if parts else ""

    # Write data — apply value mappings, preserve numeric types for non-mapped fields
    for row_idx, teacher in enumerate(teachers, 2):
        for col_idx, key in enumerate(all_columns, 1):
            # Handle combined address fields
            if key == "_permanentAddress":
                value = combine_address(teacher, PERMANENT_ADDRESS_FIELDS)
            elif key == "_currentAddress":
                value = combine_address(teacher, CURRENT_ADDRESS_FIELDS)
            elif key == "Sr No":
                value = row_idx - 1  # Sequential number (row 2 = 1, row 3 = 2, ...)
            else:
                value = teacher.get(key, "")
                if value is None:
                    value = ""
                # Apply gender code conversion
                if key == "gender" and str(value).strip() in GENDER_MAP:
                    value = GENDER_MAP[str(value).strip()]
                # Apply value mapping if available
                if value != "":
                    normalized_key = key.lower().replace("_", "").replace("-", "").replace(" ", "")
                    lookup = field_value_map.get(normalized_key) or field_value_map.get(key)
                    if lookup:
                        # Exact string lookup only; unmapped codes remain unchanged.
                        value = lookup.get(str(value).strip(), value)
            ws.cell(row=row_idx, column=col_idx, value=value)

    # Auto-fit column widths based on content
    for col_idx, key in enumerate(all_columns, 1):
        header = header_for(key)
        max_len = len(header) + 2
        for row_idx in range(2, len(teachers) + 2):
            val = ws.cell(row=row_idx, column=col_idx).value
            cell_val = str(val) if val is not None else ""
            max_len = max(max_len, len(cell_val) + 2)
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = min(max_len, 50)

    # Professional formatting matching student OTR report style
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    header_fill = PatternFill(start_color="F2F4F7", end_color="F2F4F7", fill_type="solid")
    header_font = Font(bold=True, color="1F2937", size=10)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    data_font = Font(bold=False, color="111827", size=10)
    data_alignment = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )
    for col_idx in range(1, len(all_columns) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = thin_border
    for row_idx in range(2, len(teachers) + 2):
        for col_idx in range(1, len(all_columns) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.alignment = data_alignment
            cell.border = thin_border
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(all_columns))}{len(teachers) + 1}"
    ws.freeze_panes = "A2"

    wb.save(filename)
    log.info(f"Exported {len(teachers)} teachers to {filename}")


async def main():
    uid = os.environ.get("ESHIKSHAKOSH_USERNAME", "")
    pwd = os.environ.get("ESHIKSHAKOSH_PASSWORD", "")

    if not uid or not pwd:
        print("ERROR: ESHIKSHAKOSH_USERNAME / ESHIKSHAKOSH_PASSWORD not set")
        sys.exit(1)

    # Step 1: Login and capture encrypted IDs
    print(f"\n{'='*60}")
    print("STEP 1: Login and capture encrypted IDs")
    print(f"{'='*60}")
    captured = await login_and_capture_encrypted_ids(uid, pwd)

    if not captured.get("token"):
        print("ERROR: Could not capture token")
        sys.exit(1)
    if not captured.get("schoolId"):
        print("ERROR: Could not capture encrypted schoolId")
        sys.exit(1)
    if not captured.get("userId"):
        print("ERROR: Could not capture encrypted userId")
        sys.exit(1)

    print(f"\nCaptured:")
    print(f"  Token: {captured['token'][:30]}...")
    print(f"  Access Token: {captured.get('access_token', '')[:30]}...")
    print(f"  School ID (encrypted): {captured['schoolId'][:30]}...")
    print(f"  User ID (encrypted): {captured['userId'][:30]}...")

    # Step 1.5: Get dropdown mappings (already captured during login)
    value_mappings = captured.get("dropdown_mappings", {})
    print(f"\n{'='*60}")
    print("STEP 1.5: Dropdown mappings")
    print(f"{'='*60}")
    if value_mappings:
        print(f"  Extracted {len(value_mappings)} dropdown mappings:")
        for name, opts in value_mappings.items():
            print(f"    {name}: {len(opts)} options")
    else:
        print("  ⚠️ No dropdown mappings — encoded values will remain as-is")

    # Step 2: Build session + headers
    session = build_session()
    headers = build_headers(captured["token"], captured.get("access_token", captured["token"]))

    # Step 3: Fetch all teachers
    print(f"\n{'='*60}")
    print("STEP 2: Fetch all teachers")
    print(f"{'='*60}")
    teachers = fetch_all_teachers(session, headers, captured)

    if not teachers:
        print("ERROR: No teachers fetched")
        sys.exit(1)

    print(f"\nTotal teachers fetched: {len(teachers)}")

    # Step 3.5: Try to fetch academic/education details
    print(f"\n{'='*60}")
    print("STEP 3.5: Fetching academic/education details")
    print(f"{'='*60}")
    edu_endpoints = [
        "/teacher/getTeacherEducation",
        "/teacher/educationDetails",
        "/teacher/getEducationInfo",
        "/teacher/education",
        "/teacher/getTeacherDetails",
        "/teacher/viewTeacherEducation",
    ]
    edu_success = False
    for endpoint in edu_endpoints:
        if edu_success:
            break
        try:
            sample_payload = {
                "tId": teachers[0].get("tId"),
                "encId": teachers[0].get("encId", ""),
            }
            resp = session.post(
                f"https://eshikshakosh.bihar.gov.in:8443{endpoint}",
                json=sample_payload,
                timeout=15,
            )
            print(f"  Trying {endpoint}: HTTP {resp.status_code}")
            if resp.status_code == 200:
                body = resp.json()
                if body.get("data"):
                    print(f"  ✅ {endpoint} works! Data keys: {list(body['data'].keys())[:10]}")
                    # Fetch for all teachers
                    for teacher in teachers:
                        try:
                            p = {"tId": teacher.get("tId"), "encId": teacher.get("encId", "")}
                            r = session.post(
                                f"https://eshikshakosh.bihar.gov.in:8443{endpoint}",
                                json=p,
                                timeout=15,
                            )
                            if r.status_code == 200:
                                edu_data = r.json().get("data", {})
                                if edu_data:
                                    # Flatten academic data into teacher dict
                                    for k, v in edu_data.items():
                                        teacher[f"edu_{k}"] = v
                        except Exception:
                            pass
                    edu_success = True
                else:
                    print(f"  ❌ {endpoint}: no data — {body.get('message', '')[:80]}")
            else:
                print(f"  ❌ {endpoint}: {resp.text[:100]}")
        except Exception as e:
            print(f"  ❌ {endpoint}: {e}")
    if not edu_success:
        print("  ⚠️ No academic endpoint worked — exporting without academic details")

    # Step 4: Export to Excel
    print(f"\n{'='*60}")
    print("STEP 3: Export to Excel")
    print(f"{'='*60}")

    # Create exports directory
    export_dir = os.path.expanduser("~/exports")
    os.makedirs(export_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{export_dir}/Teachers_UMV_Tetahali_{timestamp}.xlsx"
    export_to_excel(teachers, filename, value_mappings=value_mappings)

    print(f"\n{'='*60}")
    print(f"DONE! {len(teachers)} teachers exported to:")
    print(f"  {filename}")
    print(f"{'='*60}")

    # Print sample
    if teachers:
        sample = teachers[0]
        print(f"\nSample teacher ({sample.get('teacherName', 'N/A')}):")
        print(f"  tId: {sample.get('tId')}")
        print(f"  teacherLoginCode: {sample.get('teacherLoginCode')}")
        print(f"  teacherName: {sample.get('teacherName')}")
        print(f"  firstName: {sample.get('firstName')}")
        print(f"  lastName: {sample.get('lastName')}")
        print(f"  gender: {sample.get('gender')}")
        print(f"  teacherType: {sample.get('teacherType')}")
        print(f"  teacherTitle: {sample.get('teacherTitle')}")
        print(f"  mobile: {sample.get('mobile')}")
        print(f"  email: {sample.get('teacherEmail')}")
        print(f"  DOB: {sample.get('DOB')}")
        print(f"  aadhaarNo: {sample.get('aadhaarNo')}")
        print(f"  panNo: {sample.get('panNo')}")
        print(f"  gpfNo: {sample.get('gpfNo')}")
        print(f"  pranNo: {sample.get('pranNo')}")
        print(f"  uanNo: {sample.get('uanNo')}")
        print(f"  fatherName: {sample.get('fatherName')}")
        print(f"  motherName: {sample.get('motherName')}")
        print(f"  serviceJoiningDt: {sample.get('serviceJoiningDt')}")
        print(f"  schoolName: {sample.get('schoolName')}")
        print(f"  schoolUdiseCode: {sample.get('schoolUdiseCode')}")
        print(f"  Total fields: {len(sample.keys())}")


if __name__ == "__main__":
    asyncio.run(main())
