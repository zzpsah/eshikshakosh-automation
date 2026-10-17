#!/usr/bin/env python3
"""Probe teacher API response structure using the proven student API pattern."""
import asyncio
import json
import logging
import os
import re
import sys
from playwright.async_api import async_playwright
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("probe")

BASE_URL = "https://eshikshakosh.bihar.gov.in:8443"
TEACHER_LIST_URL = f"{BASE_URL}/teacher/viewTeacher"
TEACHER_DETAIL_URL = f"{BASE_URL}/teacher/getTeacherDetails"


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


async def login_and_get_tokens(uid, pwd):
    """Login via Playwright, capture JWT + access_token from response."""
    captured = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

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

        # Capture login response
        async with page.expect_response(
            lambda resp: "/auth/login" in resp.url.lower(),
            timeout=25000,
        ) as login_info:
            await page.click("input.submit__btn")

        login_resp = await login_info.value
        login_data = await login_resp.json()
        log.info(f"Login HTTP {login_resp.status}")

        # Extract both tokens
        direct_token = login_data.get("token", "")
        direct_access = login_data.get("access_token") or login_data.get("accesstoken", "")

        if isinstance(direct_token, str) and len(direct_token) > 20:
            captured["token"] = direct_token.replace("Bearer ", "").strip()
        if isinstance(direct_access, str) and len(direct_access) > 20:
            captured["access_token"] = direct_access.replace("Bearer ", "").strip()

        # Fallback: check sessionStorage
        if not captured.get("token"):
            try:
                storage = await page.evaluate("Object.fromEntries(Object.entries(sessionStorage))")
                jwt_token = str(storage.get("jwtToken") or "").strip()
                access_token = str(storage.get("access_token") or "").strip()
                if jwt_token:
                    captured["token"] = jwt_token
                    captured["access_token"] = access_token or jwt_token
                    log.info("Got tokens from sessionStorage")
            except Exception as exc:
                log.warning(f"sessionStorage check failed: {exc}")

        if captured.get("token"):
            log.info(f"Token captured: {captured['token'][:30]}...")
        if captured.get("access_token"):
            log.info(f"Access token captured: {captured['access_token'][:30]}...")

        await page.close()
        await context.close()
        await browser.close()

    return captured


def probe_teacher_list(session, headers, school_id="42645", academic_year="2026-27"):
    """Probe /teacher/viewTeacher endpoint."""
    payload = {
        "offset": "0",
        "limit": "2",
        "searchSchoolId": school_id,
        "academicYear": academic_year,
    }
    log.info(f"POST {TEACHER_LIST_URL} with payload: {payload}")
    res = session.post(TEACHER_LIST_URL, headers=headers, json=payload, timeout=35)
    log.info(f"HTTP {res.status_code}")
    if res.status_code == 200:
        data = res.json()
        return data
    else:
        log.error(f"Response: {res.text[:500]}")
        return None


def probe_teacher_detail(session, headers, teacher_id, academic_year="2026-27"):
    """Probe /teacher/getTeacherDetails endpoint."""
    # Try GET with query param
    res = session.get(
        f"{TEACHER_DETAIL_URL}?id={teacher_id}",
        headers=headers,
        timeout=15,
    )
    log.info(f"GET detail HTTP {res.status_code}")
    if res.status_code == 200:
        return res.json()

    # Try POST with body
    res = session.post(
        TEACHER_DETAIL_URL,
        headers=headers,
        json={"id": teacher_id, "academicYear": academic_year},
        timeout=15,
    )
    log.info(f"POST detail HTTP {res.status_code}")
    if res.status_code == 200:
        return res.json()

    log.error(f"Detail response: {res.text[:300]}")
    return None


async def main():
    uid = os.environ.get("ESHIKSHAKOSH_USERNAME", "")
    pwd = os.environ.get("ESHIKSHAKOSH_PASSWORD", "")

    if not uid or not pwd:
        print("ERROR: ESHIKSHAKOSH_USERNAME / ESHIKSHAKOSH_PASSWORD not set")
        sys.exit(1)

    # Step 1: Login and get tokens
    tokens = await login_and_get_tokens(uid, pwd)
    if not tokens.get("token"):
        print("ERROR: Could not capture token")
        sys.exit(1)

    # Step 2: Build session + headers
    session = build_session()
    headers = build_headers(tokens["token"], tokens.get("access_token", tokens["token"]))

    # Step 3: Probe teacher list
    print(f"\n{'='*60}")
    print("PROBE 1: /teacher/viewTeacher")
    print(f"{'='*60}")
    list_data = probe_teacher_list(session, headers)
    if list_data:
        print(f"Top-level keys: {list_data.keys()}")
        print(f"Total records: {list_data.get('totalRecord')}")
        sample = (list_data.get("data") or [None])[0]
        if sample:
            print(f"\nSample teacher keys: {list(sample.keys()) if isinstance(sample, dict) else type(sample)}")
            print(f"Sample teacher: {json.dumps(sample, indent=2, ensure_ascii=False)[:2000]}")
        else:
            print("No sample teacher found")
            print(f"Full response: {json.dumps(list_data, indent=2, ensure_ascii=False)[:1000]}")

            # Try to find any teacher ID for detail probe
            teacher_id = None
            if isinstance(sample, dict):
                for key in ["teacherId", "id", "encId", "teacherEncId"]:
                    if sample.get(key):
                        teacher_id = sample[key]
                        break

            if teacher_id:
                # Step 4: Probe teacher detail
                print(f"\n{'='*60}")
                print(f"PROBE 2: /teacher/getTeacherDetails?id={teacher_id}")
                print(f"{'='*60}")
                detail_data = probe_teacher_detail(session, headers, teacher_id)
                if detail_data:
                    print(f"Detail keys: {detail_data.keys()}")
                    detail = detail_data.get("data", detail_data)
                    if isinstance(detail, dict):
                        print(f"Detail field count: {len(detail.keys())}")
                        print(f"Detail fields: {list(detail.keys())}")
                        print(f"Full detail: {json.dumps(detail, indent=2, ensure_ascii=False)[:3000]}")
    else:
        print("ERROR: Teacher list API failed")

    print(f"\n{'='*60}")
    print("PROBE COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())
