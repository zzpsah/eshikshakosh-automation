#!/usr/bin/env python3
"""Read-only e-ShikshaKosh teacher DETAIL export (registration + education + service history).

Companion to esk_teacher_browser_extract_school.py. The list API carries an encrypted
`encId` per teacher; every detail endpoint is called with that token through the live
browser session so the portal's own auth headers apply.

Endpoints (all read-only POSTs, all keyed by the teacher's encrypted id):
    /teacher/registrationInfo          -> registration / personal / address
    /teacher/getTeacherDetails         -> basic summary
    /teacher/viewTeacherEducationInfo  -> pre-service and in-service qualifications
    /teacher/viewTeacherProfessionalInfo
    /teacher/viewTeacherOtherInfo
    /teacher/viewTeacherTrainingInfo
    /teacher/getExistingServiceInfo    -> posting history

Required env: ESHIKSHAKOSH_USERNAME, ESHIKSHAKOSH_PASSWORD, ESHIKSHAKOSH_TARGET_UDISE
Optional env: ESHIKSHAKOSH_OUT, ESHIKSHAKOSH_DETAIL_LIMIT
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

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import esk_code_maps as code_maps

BASE = 'https://eshikshakosh.bihar.gov.in'
API = 'https://eshikshakosh.bihar.gov.in:8443'
PAGE_SIZE = '100'
AUTH_HEADER_NAMES = {'accept', 'content-type', 'authorization', 'accesstoken', 'authtoken', 'authaccess'}

DETAIL_ENDPOINTS = [
    ('registrationInfo', '/teacher/registrationInfo', 'encId'),
    # '/teacher/getTeacherDetails' returns HTTP 500 "Server Error" for every key
    # (teacherId / encId / tId / teacherEncryptedId) — verified 2026-10-17. Do not re-add.
    ('educationInfo', '/teacher/viewTeacherEducationInfo', 'encId'),
    ('professionalInfo', '/teacher/viewTeacherProfessionalInfo', 'encId'),
    ('otherInfo', '/teacher/viewTeacherOtherInfo', 'encId'),
    ('trainingInfo', '/teacher/viewTeacherTrainingInfo', 'encId'),
    ('serviceInfo', '/teacher/getExistingServiceInfo', 'teacherEncryptedId'),
]


def require_env(name: str) -> str:
    value = (os.environ.get(name) or '').strip()
    if not value:
        raise RuntimeError(f'{name} is not set; refusing to guess')
    return value


def slugify(text: str) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '_', (text or '').strip()).strip('_') or 'Unknown_School'


def rows_of(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # Education returns two separate lists; tag and merge so both reach the sheet.
        pre = payload.get('preServicedata')
        ins = payload.get('inServicedata')
        if isinstance(pre, list) or isinstance(ins, list):
            merged = []
            for row in (pre or []):
                if isinstance(row, dict):
                    merged.append({**row, '_serviceType': 'Pre-Service'})
            for row in (ins or []):
                if isinstance(row, dict):
                    merged.append({**row, '_serviceType': 'In-Service'})
            return merged
        for key in ('serviceInfo', 'educationInfo', 'data'):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for sub in ('data', 'list', 'records', 'result'):
                    if isinstance(value.get(sub), list):
                        return value[sub]
    return []


def unpack(response_json):
    if not isinstance(response_json, dict):
        return [], 0
    rows = response_json.get('data', [])
    total = response_json.get('totalRecord', 0)
    if isinstance(rows, dict):
        total = rows.get('totalRecord', total)
        rows = rows.get('data', [])
    if not isinstance(rows, list):
        rows = []
    try:
        total = int(total or len(rows))
    except (ValueError, TypeError):
        total = len(rows)
    return rows, total


async def main():
    uid = require_env('ESHIKSHAKOSH_USERNAME')
    pwd = require_env('ESHIKSHAKOSH_PASSWORD')
    target_udise = require_env('ESHIKSHAKOSH_TARGET_UDISE')
    out_dir = Path(os.environ.get('ESHIKSHAKOSH_OUT') or (Path.home() / 'exports'))
    limit = os.environ.get('ESHIKSHAKOSH_DETAIL_LIMIT')

    print(f'TARGET_UDISE={target_udise}')

    auth = {}
    teachers, total = [], 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        async def capture_auth(route):
            req = route.request
            try:
                payload = json.loads(req.post_data or '{}')
            except (json.JSONDecodeError, TypeError):
                await route.continue_()
                return
            payload['offset'] = '0'
            payload['limit'] = PAGE_SIZE
            payload['schoolUdiseCode'] = target_udise
            hdrs = await req.all_headers()
            auth.update({k.lower(): v for k, v in hdrs.items() if k.lower() in AUTH_HEADER_NAMES})
            await route.continue_(post_data=json.dumps(payload))

        await page.route('**/teacher/viewTeacher', capture_auth)
        try:
            await page.goto(BASE, wait_until='networkidle', timeout=90000)
            if await page.locator('#radio2').count():
                await page.click('#radio2')
                await page.wait_for_timeout(300)
            await page.locator("input[formcontrolname='userId']").wait_for(state='visible', timeout=15000)
            await page.fill("input[formcontrolname='userId']", uid)
            await page.fill("input[formcontrolname='password']", pwd)
            captcha = await page.inner_text('.capcha__head')
            m = re.search(r'(\d+)\s*([+\-*])\s*(\d+)', captcha)
            if not m:
                raise RuntimeError('Portal captcha format was not recognized; no login attempted')
            a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
            await page.fill("input[placeholder='Enter User Captcha']", str(a + b if op == '+' else a - b if op == '-' else a * b))
            async with page.expect_response(lambda r: '/auth/login' in r.url.lower(), timeout=35000) as login_info:
                await page.click('input.submit__btn')
            login_resp = await login_info.value
            print(f'LOGIN_HTTP={login_resp.status}')
            if login_resp.status != 200:
                raise RuntimeError(f'Portal login failed with HTTP {login_resp.status}')
            login_json = await login_resp.json()
            if login_json.get('success') is False:
                raise RuntimeError('Portal rejected login credentials')
            await page.wait_for_timeout(1200)

            await page.goto(f'{BASE}/Application/teacher/registration/viewTeacher', wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2000)
            search = page.locator("button:has-text('Search')")
            if not await search.count():
                raise RuntimeError('Teacher Search button was not found after login')
            async with page.expect_response(lambda r: '/teacher/viewTeacher' in r.url and r.request.method == 'POST', timeout=45000) as teacher_info:
                await search.first.click()
            first_json = await (await teacher_info.value).json()
            teachers, total = unpack(first_json)
            if not teachers:
                raise RuntimeError('Browser teacher-list response contained no teacher records')
            if not auth:
                raise RuntimeError('Could not capture the browser request context safely')

            while len(teachers) < total:
                offset = len(teachers)
                payload = {'offset': str(offset), 'limit': PAGE_SIZE, 'schoolUdiseCode': target_udise}
                res = await page.evaluate("""async ({url, payload, headers}) => {
                    const r = await fetch(url, {method:'POST', headers, body:JSON.stringify(payload)});
                    let body; try { body = await r.json(); } catch (_) { body = null; }
                    return {status:r.status, body};
                }""", {'url': f'{API}/teacher/viewTeacher', 'payload': payload, 'headers': auth})
                if res.get('status') != 200:
                    raise RuntimeError(f'Pagination failed with HTTP {res.get("status")}')
                nxt, nxt_total = unpack(res.get('body'))
                if not nxt:
                    raise RuntimeError(f'Pagination stopped at {len(teachers)} of {total}; refusing partial export')
                teachers.extend(nxt)
                total = max(total, nxt_total)
            if len(teachers) < total:
                raise RuntimeError(f'Only {len(teachers)} of {total} records retrieved; refusing partial export')

            wrong = [t for t in teachers if str(t.get('schoolUdiseCode') or '').strip() != target_udise]
            if wrong:
                raise RuntimeError(f'Scope validation failed: {len(wrong)} rows do not match UDISE {target_udise}; refusing export')

            if limit:
                teachers = teachers[: int(limit)]
                print(f'LIMIT_APPLIED={len(teachers)}')

            async def call(path, payload):
                res = await page.evaluate("""async ({url, payload, headers}) => {
                    const r = await fetch(url, {method:'POST', headers, body:JSON.stringify(payload)});
                    let body; try { body = await r.json(); } catch (_) { body = null; }
                    return {status:r.status, body};
                }""", {'url': API + path, 'payload': payload, 'headers': auth})
                return res

            details = []
            for idx, teacher in enumerate(teachers, 1):
                enc = str(teacher.get('encId') or '').strip()
                if not enc:
                    print(f'WARNING teacher {teacher.get("teacherName")} has no encId; detail sections skipped')
                    details.append({'teacher': teacher, 'sections': {}})
                    continue
                sections = {}
                for name, path, key in DETAIL_ENDPOINTS:
                    try:
                        res = await call(path, {key: enc})
                        body = res.get('body')
                        if res.get('status') != 200:
                            sections[name] = {'error': f'HTTP {res.get("status")}'}
                        else:
                            sections[name] = body if isinstance(body, dict) else {'data': body}
                    except Exception as exc:  # keep going; report the failed section
                        sections[name] = {'error': f'{type(exc).__name__}: {exc}'}
                details.append({'teacher': teacher, 'sections': sections})
                print(f'DETAIL {idx}/{len(teachers)} {teacher.get("teacherName")} sections={len(sections)}')
                await page.wait_for_timeout(400)
        finally:
            await context.close()
            await browser.close()

    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    school_slug = slugify(str(teachers[0].get('schoolName') or '')) if teachers else slugify(target_udise)
    output = out_dir / f'Teacher_Details_{school_slug}_{timestamp}.xlsx'
    write_workbook(teachers, details, str(output))

    # Teach the code->label map from the portal's own service-history labels, so later
    # list exports can show readable subject names instead of numeric codes.
    learned = {}
    for item in details:
        section = (item.get('sections') or {}).get('serviceInfo') or {}
        learned.update(code_maps.learn_from_service_history(_rows(section)))
    if learned:
        code_maps.save(code_maps.merge(code_maps.load(), 'appointedSubject', learned))
        print(f'SUBJECT_MAP_LEARNED={len(learned)}')

    os.chmod(output, 0o600)
    print(f'TEACHERS={len(teachers)}')
    print(f'WORKBOOK={output}')
    print('SOURCE=authenticated Playwright browser session; read-only')


def _rows(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        # Education returns two separate lists; tag and merge so both reach the sheet.
        pre = value.get('preServicedata')
        ins = value.get('inServicedata')
        if isinstance(pre, list) or isinstance(ins, list):
            merged = []
            for row in (pre or []):
                if isinstance(row, dict):
                    merged.append({**row, '_serviceType': 'Pre-Service'})
            for row in (ins or []):
                if isinstance(row, dict):
                    merged.append({**row, '_serviceType': 'In-Service'})
            return merged
        for key in ('serviceInfo', 'educationInfo', 'data', 'list', 'records', 'result'):
            inner = value.get(key)
            if isinstance(inner, list):
                return inner
            if isinstance(inner, dict):
                for sub in ('data', 'list', 'records', 'result'):
                    if isinstance(inner.get(sub), list):
                        return inner[sub]
    return []


def write_workbook(teachers, details, filename):
    import openpyxl
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    bold = Font(bold=True)

    # Sheet 1 — the list itself
    ws = wb.active
    ws.title = 'Teachers'
    headers = ['S.No.', 'Teacher ID', 'Temp Login ID', 'Teacher Name', 'Title', 'Nature of Appointment',
               'Mobile', 'School', 'UDISE', 'Service Joining', 'Current School Joining', 'Appointed Subject']
    ws.append(headers)
    for c in ws[1]:
        c.font = bold
    for i, t in enumerate(teachers, 1):
        ws.append([i, t.get('tId'), t.get('teacherLoginCode'), t.get('teacherName'), t.get('teacherTitle'),
                   t.get('natureOfAppointmt'), t.get('mobile'), t.get('schoolName'), t.get('schoolUdiseCode'),
                   t.get('serviceJoiningDt'), t.get('joiningCurrentSchoolDt'), t.get('appointedSubject')])

    # Sheet 2 — registration / personal details, one row per teacher
    ws = wb.create_sheet('Registration Info')
    reg_keys = ['tId', 'teacherName', 'prefix', 'firstName', 'middleName', 'lastName', 'gender', 'DOB',
                'socialCategory', 'religion', 'mobile', 'aadhaarNo', 'teacherTitle', 'natureOfAppointmt',
                'serviceJoiningDt', 'appointedSubject', 'classCategory', 'appointmentType', 'appointingAuth',
                'joiningCurrentSchoolDt', 'bpscRollNo', 'employeeCode', 'panNo', 'gpfNo', 'pranNo', 'uanNo',
                'fatherName', 'motherName', 'spouseName', 'maritalStatus', 'teacherEmail', 'bloodGroup',
                'disabilityStatus', 'awardStatus', 'pDomicileNumber', 'pDomicile', 'schoolUdiseCode',
                'pHouseName', 'pStreet', 'pPostOffice', 'pPanchayat', 'pVillage', 'pPIN', 'pDistrictId', 'pBlockId', 'pStateName',
                'cHouseName', 'cStreet', 'cPostOffice', 'cPanchayat', 'cVillage', 'cPIN', 'cDistrictId', 'cBlockId', 'cStateName']
    ws.append(reg_keys)
    for c in ws[1]:
        c.font = bold
    for item in details:
        sec = (item.get('sections') or {}).get('registrationInfo') or {}
        data = sec.get('data') if isinstance(sec, dict) else None
        if not isinstance(data, dict):
            data = {}
        ws.append([data.get(k, '') for k in reg_keys])

    # Sheets 3..N — repeating sections, one row per record
    for sheet_name, section_name, extra_cols in [
        ('Education', 'educationInfo', ['Qualification']),
        ('Professional', 'professionalInfo', ['Qualification']),
        ('Other Info', 'otherInfo', ['Field']),
        ('Training', 'trainingInfo', ['Training']),
        ('Service History', 'serviceInfo', ['Designation']),
    ]:
        ws = wb.create_sheet(sheet_name)
        written = 0
        for item in details:
            teacher = item.get('teacher') or {}
            sec = (item.get('sections') or {}).get(section_name) or {}
            if isinstance(sec, dict) and sec.get('error'):
                continue
            records = _rows(sec)
            if not records:
                continue
            keys = list(records[0].keys()) if isinstance(records[0], dict) else []
            if written == 0:
                ws.append(['Teacher ID', 'Teacher Name'] + keys)
                for c in ws[1]:
                    c.font = bold
            for rec in records:
                row_data = [teacher.get('tId'), teacher.get('teacherName')]
                for k in keys:
                    v = rec.get(k, '') if isinstance(rec, dict) else ''
                    if isinstance(v, (list, dict)):
                        v = json.dumps(v, ensure_ascii=False)
                    row_data.append(v)
                ws.append(row_data)
                written += 1
        if written == 0:
            ws.append(['Teacher ID', 'Teacher Name', 'Status'])
            ws.append(['', '', 'No records for this school'])

    for ws in wb.worksheets:
        for col in range(1, min(ws.max_column, 80) + 1):
            width = len(str(ws.cell(row=1, column=col).value or ''))
            for row in range(2, min(ws.max_row, 60) + 1):
                val = ws.cell(row=row, column=col).value
                width = max(width, len(str(val)) if val is not None else 0)
            ws.column_dimensions[get_column_letter(col)].width = min(width + 2, 40)

    wb.save(filename)


if __name__ == '__main__':
    asyncio.run(main())
