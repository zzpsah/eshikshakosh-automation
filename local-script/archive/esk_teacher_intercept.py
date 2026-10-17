#!/usr/bin/env python3
"""Intercept actual teacher list API call from browser to discover correct payload."""
import asyncio
import json
import logging
import os
import re
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("intercept")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        # Capture all API requests
        api_calls = []

        async def on_request(request):
            if "/teacher/" in request.url or "/auth/" in request.url:
                api_calls.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "post_data": request.post_data,
                })
                log.info(f"REQUEST: {request.method} {request.url}")
                if request.post_data:
                    log.info(f"  Body: {request.post_data[:500]}")

        async def on_response(response):
            if "/teacher/" in response.url:
                try:
                    body = await response.json()
                    log.info(f"RESPONSE: {response.url} -> HTTP {response.status}")
                    log.info(f"  Keys: {list(body.keys()) if isinstance(body, dict) else type(body)}")
                    if isinstance(body, dict) and body.get("data"):
                        sample = body["data"][0] if isinstance(body["data"], list) else body["data"]
                        if isinstance(sample, dict):
                            log.info(f"  Sample keys: {list(sample.keys())}")
                            log.info(f"  Sample: {json.dumps(sample, ensure_ascii=False)[:1000]}")
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # Login
        await page.goto("https://eshikshakosh.bihar.gov.in",
                        wait_until="networkidle", timeout=35000)
        await page.click("#radio2")
        await page.wait_for_timeout(400)

        uid = os.environ.get("ESHIKSHAKOSH_USERNAME", "")
        pwd = os.environ.get("ESHIKSHAKOSH_PASSWORD", "")

        await page.fill("input[formcontrolname='userId']", uid)
        await page.fill("input[formcontrolname='password']", pwd)

        captcha_text = await page.inner_text(".capcha__head")
        match = re.search(r"(\d+)\s*([+\-*])\s*(\d+)", captcha_text)
        if match:
            left, op, right = int(match.group(1)), match.group(2), int(match.group(3))
            answer = left + right if op == "+" else left - right if op == "-" else left * right
            await page.fill("input[placeholder='Enter User Captcha']", str(answer))

        await page.click("input.submit__btn")
        await page.wait_for_url("**/dashboard", timeout=15000)
        log.info("Login OK")

        # Navigate to teacher registration page
        await page.goto(
            "https://eshikshakosh.bihar.gov.in/Application/teacher/registration/viewTeacher",
            wait_until="networkidle", timeout=35000,
        )
        await page.wait_for_timeout(3000)

        # Click Search button if exists
        try:
            search_btn = page.locator("button:has-text('Search'), button:has-text('search'), input[type='submit'][value*='Search']")
            if await search_btn.count() > 0:
                await search_btn.first.click()
                log.info("Clicked Search button")
                await page.wait_for_timeout(3000)
        except Exception as e:
            log.warning(f"Search button: {e}")

        # Print all captured API calls
        print(f"\n{'='*60}")
        print(f"CAPTURED {len(api_calls)} API CALLS")
        print(f"{'='*60}")
        for i, call in enumerate(api_calls):
            print(f"\n--- Call {i+1} ---")
            print(f"URL: {call['url']}")
            print(f"Method: {call['method']}")
            if call.get('post_data'):
                print(f"Body: {call['post_data']}")
            # Print relevant headers
            for key in ['authorization', 'accesstoken', 'authtoken', 'authaccess', 'content-type']:
                if key in call.get('headers', {}):
                    val = call['headers'][key]
                    if 'token' in key.lower() or 'auth' in key.lower():
                        print(f"Header {key}: {val[:50]}...")
                    else:
                        print(f"Header {key}: {val}")

        await page.close()
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
