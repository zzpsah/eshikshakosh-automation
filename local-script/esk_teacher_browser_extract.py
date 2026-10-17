#!/usr/bin/env python3
"""Read-only e-ShikshaKosh teacher export using the authenticated Playwright browser session.

Credentials are supplied only by the existing Bitwarden-backed eshikshakosh-run wrapper.
The script reads the live UI's /teacher/viewTeacher request and reuses its browser auth
headers for pagination. It never prints tokens, encrypted identifiers, or teacher PII.
"""
from __future__ import annotations
import asyncio
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import esk_teacher_extract as legacy  # reuse the established Excel field/header mapping

BASE = 'https://eshikshakosh.bihar.gov.in'
API_URL = 'https://eshikshakosh.bihar.gov.in:8443/teacher/viewTeacher'
EXPECTED_UDISE = '10160203806'  # UMV Tetahali; refuse exports that include other schools
EXPECTED_SCHOOL_ID = 42645


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
    uid = os.environ.get('ESHIKSHAKOSH_USERNAME', '')
    pwd = os.environ.get('ESHIKSHAKOSH_PASSWORD', '')
    if not uid or not pwd:
        raise RuntimeError('Bitwarden-backed wrapper did not provide eShikshaKosh credentials')

    capture = {'payload': None, 'headers': None, 'api_seen': 0}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        async def route_teacher(route):
            req = route.request
            try:
                payload = json.loads(req.post_data or '{}')
            except (json.JSONDecodeError, TypeError):
                await route.continue_()
                return
            # Only adjust the live UI's own read-only teacher-list request.
            payload['offset'] = '0'
            payload['limit'] = '100'
            # Explicitly scope the report to UMV Tetahali, rather than exporting all schools.
            payload['searchSchoolId'] = EXPECTED_SCHOOL_ID
            payload['schoolUdiseCode'] = EXPECTED_UDISE
            hdrs = await req.all_headers()
            capture['payload'] = payload
            capture['headers'] = {k: v for k, v in hdrs.items() if k.lower() in {
                'accept', 'content-type', 'authorization', 'accesstoken', 'authtoken', 'authaccess'
            }}
            capture['api_seen'] += 1
            await route.continue_(post_data=json.dumps(payload))

        await page.route('**/teacher/viewTeacher', route_teacher)
        try:
            await page.goto(BASE, wait_until='networkidle', timeout=90000)
            # Use the teacher-role login form already used by the existing portal workflow.
            if await page.locator('#radio2').count():
                await page.click('#radio2')
                await page.wait_for_timeout(300)
            await page.locator("input[formcontrolname='userId']").wait_for(state='visible', timeout=15000)
            await page.fill("input[formcontrolname='userId']", uid)
            await page.fill("input[formcontrolname='password']", pwd)
            captcha = await page.inner_text('.capcha__head')
            import re
            m = re.search(r'(\d+)\s*([+\-*])\s*(\d+)', captcha)
            if not m:
                raise RuntimeError('Portal captcha format was not recognized; no login attempted')
            a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
            answer = a + b if op == '+' else a - b if op == '-' else a * b
            await page.fill("input[placeholder='Enter User Captcha']", str(answer))
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
            await page.wait_for_timeout(1500)
            search = page.locator("button:has-text('Search')")
            if not await search.count():
                raise RuntimeError('Teacher Search button was not found after login')
            async with page.expect_response(lambda r: '/teacher/viewTeacher' in r.url and r.request.method == 'POST', timeout=45000) as teacher_info:
                await search.first.click()
            response = await teacher_info.value
            print(f'TEACHER_API_HTTP={response.status}')
            if response.status != 200:
                raise RuntimeError(f'Teacher-list request failed with HTTP {response.status}')
            first_json = await response.json()
            teachers, total = unpack(first_json)
            if not teachers:
                raise RuntimeError('Browser teacher-list response contained no teacher records')
            if not capture['payload'] or not capture['headers']:
                raise RuntimeError('Could not capture the browser request context safely')

            # If more than one page is needed, continue with browser fetch using only the
            # auth headers from the successful, live UI request; never use a separate requests session.
            while len(teachers) < total:
                offset = len(teachers)
                payload = dict(capture['payload'])
                payload['offset'] = str(offset)
                payload['limit'] = '100'
                result = await page.evaluate("""async ({url, payload, headers}) => {
                    const r = await fetch(url, {method:'POST', headers, body:JSON.stringify(payload)});
                    let body; try { body = await r.json(); } catch (_) { body = null; }
                    return {status:r.status, body};
                }""", {'url': API_URL, 'payload': payload, 'headers': capture['headers']})
                if result.get('status') != 200:
                    raise RuntimeError(f'Browser-authenticated pagination failed with HTTP {result.get("status")}')
                next_rows, next_total = unpack(result.get('body'))
                if not next_rows:
                    raise RuntimeError(f'Pagination stopped at {len(teachers)} of {total}; refusing partial export')
                teachers.extend(next_rows)
                total = max(total, next_total)
            if len(teachers) < total:
                raise RuntimeError(f'Only {len(teachers)} of {total} records were retrieved; refusing partial export')

            # Validate the school scope and reject duplicate teacher rows before writing any workbook.
            wrong_school = [t for t in teachers if str(t.get('schoolUdiseCode') or '').strip() != EXPECTED_UDISE]
            if wrong_school:
                raise RuntimeError(f'Scope validation failed: {len(wrong_school)} records do not match target UDISE {EXPECTED_UDISE}; refusing export')
            teacher_ids = [str(t.get('tId') or '').strip() for t in teachers]
            if len(set(teacher_ids)) != len(teacher_ids):
                raise RuntimeError('Duplicate teacher IDs returned by report pagination; refusing export')

            # Capture the actual dropdown value -> label pairs rendered by the live report UI.
            # Do not guess labels for numeric codes; only translate when the portal exposes a mapping.
            value_mappings = await page.evaluate("""() => {
                const result = {};
                const selects = Array.from(document.querySelectorAll('select'));
                selects.forEach((sel, idx) => {
                    let label = '';
                    if (sel.id) {
                        const el = document.querySelector("label[for='" + sel.id + "']");
                        if (el) label = el.textContent.trim();
                    }
                    if (!label && sel.labels && sel.labels.length) label = Array.from(sel.labels).map(x => x.textContent.trim()).join(' ').trim();
                    const name = sel.name || sel.id || label || `select_${idx}`;
                    const options = Array.from(sel.options).map(o => ({value:o.value, text:o.text.trim()}))
                        .filter(o => o.value !== '' && o.text !== '' && !/^select|choose|--/i.test(o.text));
                    if (options.length) result[name] = options;
                });
                return result;
            }""")
            print(f'DROPDOWN_MAPPINGS_CAPTURED={len(value_mappings)}')
            value_mappings = {k: value_mappings[k] for k in ('searchNatureOfAppointmt', 'searchDeputationWise', 'select_5', 'select_6', 'select_7', 'select_10', 'select_11') if k in value_mappings}
            if not value_mappings:
                print('WARNING=No verified display-value mapping captured; unmapped codes will remain unchanged')

            export_dir = Path.home() / 'exports'
            export_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output = export_dir / f'Teachers_UMV_Tetahali_browser_{timestamp}.xlsx'
            legacy.export_to_excel(teachers, str(output), value_mappings=value_mappings)
            os.chmod(output, 0o600)
            print(f'TEACHERS_EXPORTED={len(teachers)}')
            print(f'FIELDS_PER_RECORD={len(teachers[0])}')
            print(f'WORKBOOK={output}')
            print('SOURCE=authenticated Playwright browser request/response; read-only')
        finally:
            await context.close()
            await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
