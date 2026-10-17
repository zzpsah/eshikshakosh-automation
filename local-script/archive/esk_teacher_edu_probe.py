#!/usr/bin/env python3
"""Probe for teacher academic/education details endpoint using working login pattern."""
import asyncio
import json
import os
import sys
import requests
from playwright.async_api import async_playwright

def get_env(name):
    val = os.environ.get(name)
    if not val:
        print(f"ERROR: {name} not set")
        sys.exit(1)
    return val

def get_udise_from_username(username):
    parts = username.split("_")
    school_part = "_".join(parts[1:-2])
    udise_map = {
        "UMV_TETAHALI": "10160203806",
        "UMV_SAHASPUR": "10130106304",
    }
    return udise_map.get(school_part, "")

async def capture_auth():
    username = get_env("ESHIKSHAKOSH_USERNAME")
    password = get_env("ESHIKSHAKOSH_PASSWORD")
    school_id = get_udise_from_username(username)
    if not school_id:
        school_id = os.environ.get("ESHIKSHAKOSH_SCHOOL_ID", "")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://eshikshakosh.bihar.gov.in", wait_until="networkidle", timeout=90000)

        # Use exact same login pattern as working browser extract script
        if await page.locator('#radio2').count():
            await page.click('#radio2')
            await page.wait_for_timeout(300)
        await page.locator("input[formcontrolname='userId']").wait_for(state='visible', timeout=15000)
        await page.fill("input[formcontrolname='userId']", school_id)
        await page.fill("input[formcontrolname='password']", password)

        # Solve captcha (same as working script)
        import re
        captcha_text = await page.inner_text('.capcha__head')
        m = re.search(r'(\d+)\s*([+\-*])\s*(\d+)', captcha_text)
        if m:
            a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
            answer = a + b if op == '+' else a - b if op == '-' else a * b
            await page.fill("input[placeholder='Enter User Captcha']", str(answer))

        # Click login and capture response
        async with page.expect_response(
            lambda r: "/auth/login" in r.url.lower(),
            timeout=60000,
        ) as login_info:
            await page.click("input.submit__btn")
        login_resp = await login_info.value
        body = await login_resp.json()
        token = body.get("token", "")
        access_token = body.get("access_token", "")

        # Fallback to sessionStorage
        if not token:
            stored = await page.evaluate("""() => ({
                token: sessionStorage.getItem('jwtToken') || localStorage.getItem('jwtToken'),
                access_token: sessionStorage.getItem('access_token') || localStorage.getItem('access_token')
            })""")
            token = stored.get("token", "") or ""
            access_token = stored.get("access_token", "") or ""

        if not token:
            await browser.close()
            return None, None, None, None

        # Navigate to teacher page and intercept teacherCount
        await page.goto(
            f"https://eshikshakosh.bihar.gov.in:8443/school/teacher-registration?schoolId={school_id}&academicYear=2026-2027",
            wait_until="networkidle",
            timeout=60000
        )

        # Intercept teacherCount to get encrypted IDs
        enc_school_id = ""
        enc_user_id = ""
        try:
            async with page.expect_response(
                lambda r: "/teacher/teacherCount" in r.url,
                timeout=30000
            ) as resp2_info:
                resp2 = await resp2_info.value
            body2 = await resp2.json()
            data = body2.get("data", {})
            enc_school_id = data.get("schoolId", "")
            enc_user_id = data.get("userId", "")
        except Exception as e:
            print(f"TeacherCount intercept failed: {e}")

        await browser.close()
        return token, access_token, enc_school_id, enc_user_id

def build_headers(token, access_token):
    return {
        "authorization": f"Bearer {token}",
        "accesstoken": f"Bearer {access_token}",
        "authtoken": f"Bearer {token}",
        "authaccess": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

async def main():
    token, access_token, enc_school_id, enc_user_id = await capture_auth()
    if not token:
        print("ERROR: Could not capture token")
        return

    print(f"Token: {token[:50]}...")
    print(f"Access token: {access_token[:50]}...")
    print(f"Encrypted schoolId: {enc_school_id[:50]}...")
    print(f"Encrypted userId: {enc_user_id[:50]}...")

    headers = build_headers(token, access_token)

    # Get a sample teacher ID first
    list_payload = {
        "offset": "0", "limit": "1", "serviceType": "Search",
        "searchDistrictId": 16, "searchBlockId": 219, "searchClusterId": 2471,
        "searchSchoolId": 42645,
        "schoolId": enc_school_id, "userId": enc_user_id,
        "loginUserTypeId": 2, "district": 16, "block": 219, "cluster": 2471,
        "searchTeacherTitle": "", "searchNatureOfAppointmt": "", "searchTeacherId": "",
        "schoolUdiseCode": "", "searchTeacherTempLoginId": "", "searchTeacherName": "",
        "searchStatusWise": "", "searchVerification": "", "searchDeputationWise": "",
        "searchTeacherSubTitle": "", "searchSchoolManagement": "", "searchSchoolCategory": "",
        "scDistrictName": "", "scBlockName": "", "scClusterName": "", "scSchoolName": "",
        "scAppointmtName": "", "scTeacherTypeName": "", "scManagementName": "",
        "scStatusName": "", "scDeputName": "", "scTeacherSubTypeName": "",
    }

    resp = requests.post(
        "https://eshikshakosh.bihar.gov.in:8443/teacher/viewTeacher",
        json=list_payload, headers=headers, timeout=30
    )
    if resp.status_code != 200:
        print(f"List API failed: {resp.status_code}")
        return

    teachers = resp.json().get("data", {}).get("data", [])
    if not teachers:
        print("No teachers found")
        return

    sample = teachers[0]
    teacher_id = sample.get("tId")
    enc_id = sample.get("encId", "")
    print(f"\nSample teacher: {sample.get('teacherName')} (tId={teacher_id}, encId={enc_id})")

    # Try education endpoints
    endpoints = [
        "/teacher/getTeacherEducation",
        "/teacher/educationDetails",
        "/teacher/getEducationInfo",
        "/teacher/education",
        "/teacher/getTeacherDetails",
        "/teacher/viewTeacherEducation",
        "/teacher/getTeacherEdu",
        "/teacher/teacherEducation",
    ]

    for endpoint in endpoints:
        try:
            resp = requests.post(
                f"https://eshikshakosh.bihar.gov.in:8443{endpoint}",
                json={"tId": teacher_id, "encId": enc_id},
                headers=headers, timeout=15
            )
            print(f"\n{endpoint}: {resp.status_code}")
            if resp.status_code == 200:
                body = resp.json()
                if body.get("data"):
                    print(f"  -> {json.dumps(body['data'], indent=2)[:500]}")
                else:
                    print(f"  -> No data: {body.get('message', '')[:100]}")
            else:
                print(f"  -> {resp.text[:150]}")
        except Exception as e:
            print(f"\n{endpoint}: ERROR - {e}")

asyncio.run(main())
