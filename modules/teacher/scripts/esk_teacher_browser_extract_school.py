#!/usr/bin/env python3
"""Read-only e-ShikshaKosh teacher export for ANY school.

Nothing is hardcoded: credentials, target school and output directory all come from
the environment, so the same script works for every school.

Required:
    ESHIKSHAKOSH_USERNAME      portal login id (11-digit UDISE or teacher id)
    ESHIKSHAKOSH_PASSWORD      portal password
    ESHIKSHAKOSH_TARGET_UDISE  UDISE of the school whose teachers are exported

Optional:
    ESHIKSHAKOSH_OUT           directory for the workbook (default ~/exports)

The school's district/block/cluster and the encrypted schoolId/userId are read from
the live portal request of the logged-in user; only offset/limit and the UDISE filter
are overridden. The export aborts unless every returned row matches the target UDISE.
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
import esk_teacher_extract as legacy  # reuse the established Excel field/header mapping
import esk_code_maps as code_maps

BASE = 'https://eshikshakosh.bihar.gov.in'
API_URL = 'https://eshikshakosh.bihar.gov.in:8443/teacher/viewTeacher'
PAGE_SIZE = '100'


def require_env(name: str) -> str:
    value = (os.environ.get(name) or '').strip()
    if not value:
        raise RuntimeError(f'{name} is not set; refusing to guess')
    return value


def slugify(text: str) -> str:
    slug = re.sub(r'[^A-Za-z0-9]+', '_', (text or '').strip()).strip('_')
    return slug or 'Unknown_School'


def target_udise():
    return require_env('ESHIKSHAKOSH_TARGET_UDISE')


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


def slug_from_schools(teachers):
    for teacher in teachers:
        raw = str(teacher.get('schoolName') or '').strip()
        if raw:
            return slugify(raw)
    return None


async def main():
    uid = require_env('ESHIKSHAKOSH_USERNAME')
    pwd = require_env('ESHIKSHAKOSH_PASSWORD')
    expected_udise = target_udise()
    out_dir = Path(os.environ.get('ESHIKSHAKOSH_OUT') or (Path.home() / 'exports'))

    print(f'TARGET_UDISE={expected_udise}')

    capture = {'payload': None, 'headers': None}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        # Only widen page size and re-scope the UDISE filter. District/block/cluster and
        # the encrypted schoolId/userId stay exactly as the portal sent them for this login.
        async def route_teacher(route):
            req = route.request
            try:
                payload = json.loads(req.post_data or '{}')
            except (json.JSONDecodeError, TypeError):
                await route.continue_()
                return
            payload['offset'] = '0'
            payload['limit'] = PAGE_SIZE
            payload['schoolUdiseCode'] = expected_udise
            hdrs = await req.all_headers()
            capture['payload'] = payload
            capture['headers'] = {k: v for k, v in hdrs.items() if k.lower() in {
                'accept', 'content-type', 'authorization', 'accesstoken', 'authtoken', 'authaccess'
            }}
            await route.continue_(post_data=json.dumps(payload))

        await page.route('**/teacher/viewTeacher', route_teacher)
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
            await page.wait_for_timeout(2000)
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

            while len(teachers) < total:
                offset = len(teachers)
                payload = dict(capture['payload'])
                payload['offset'] = str(offset)
                payload['limit'] = PAGE_SIZE
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

            wrong_school = [t for t in teachers if str(t.get('schoolUdiseCode') or '').strip() != expected_udise]
            if wrong_school:
                raise RuntimeError(f'Scope validation failed: {len(wrong_school)} records do not match target UDISE {expected_udise}; refusing export')
            teacher_ids = [str(t.get('tId') or '').strip() for t in teachers]
            if len(set(teacher_ids)) != len(teacher_ids):
                raise RuntimeError('Duplicate teacher IDs returned by report pagination; refusing export')

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
            value_mappings = {k: value_mappings[k] for k in ('searchNatureOfAppointmt', 'searchDeputationWise', 'select_5', 'select_6', 'select_7', 'select_10', 'select_11') if k in value_mappings}
            if not value_mappings:
                print('WARNING=No verified display-value mapping captured; unmapped codes will remain unchanged')

            out_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            school_slug = slug_from_schools(teachers) or slugify(expected_udise)
            output = out_dir / f'Teachers_{school_slug}_browser_{timestamp}.xlsx'
            legacy.export_to_excel(teachers, str(output), value_mappings=value_mappings)
            # Replace numeric subject codes with the labels learned from the portal's own
            # service-history records (see esk_code_maps.py).
            mapped = code_maps.apply_to_workbook(str(output), 'Appointed Subject', code_maps.subject_map())
            os.chmod(output, 0o600)
            print(f'SCHOOL_NAME={teachers[0].get("schoolName", "")}')
            print(f'TEACHERS_EXPORTED={len(teachers)}')
            print(f'FIELDS_PER_RECORD={len(teachers[0])}')
            print(f'SUBJECT_CODES_MAPPED={mapped}')
            print(f'WORKBOOK={output}')
            print('SOURCE=authenticated Playwright browser request/response; read-only')
        finally:
            await context.close()
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
