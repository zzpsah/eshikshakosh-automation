#!/usr/bin/env python3
"""Intercept teacher detail API call by clicking 'Print Teacher Details' button."""
import asyncio
import json
import os
import sys
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

async def main():
    username = get_env("ESHIKSHAKOSH_USERNAME")
    password = get_env("ESHIKSHAKOSH_PASSWORD")
    school_id = get_udise_from_username(username)
    if not school_id:
        school_id = os.environ.get("ESHIKSHAKOSH_SCHOOL_ID", "")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Track all API calls
        api_calls = []
        def on_request(request):
            if "/teacher/" in request.url and request.method == "POST":
                try:
                    body = request.post_data
                    api_calls.append({
                        "url": request.url,
                        "method": request.method,
                        "body": body[:500] if body else "",
                    })
                except:
                    pass

        page.on("request", on_request)

        # Login
        await page.goto("https://eshikshakosh.bihar.gov.in", wait_until="networkidle", timeout=90000)
        udise_input = page.locator("input[placeholder='11-Digit UDISE Code']")
        await udise_input.fill(school_id)
        await page.fill("input[placeholder='Password']", password)
        await page.wait_for_timeout(500)

        # Solve captcha
        await page.evaluate("""() => {
            const caps = document.querySelectorAll('.badge');
            caps.forEach(c => { if (c.offsetWidth > 0 && c.offsetHeight > 0) c.click(); });
        }""")
        await page.wait_for_timeout(500)

        # Click login
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const loginBtn = btns.find(b => b.textContent.trim().toLowerCase().includes('login'));
            if (loginBtn) loginBtn.click();
        }""")

        # Wait for login
        await page.wait_for_response(lambda r: "/auth/login" in r.url, timeout=60000)
        await page.wait_for_timeout(2000)

        # Navigate to teacher page
        await page.goto(
            f"https://eshikshakosh.bihar.gov.in:8443/school/teacher-registration?schoolId={school_id}&academicYear=2026-2027",
            wait_until="networkidle",
            timeout=60000
        )
        await page.wait_for_timeout(3000)

        # Click Search button
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const searchBtn = btns.find(b => b.textContent.trim().toLowerCase().includes('search'));
            if (searchBtn) searchBtn.click();
        }""")
        await page.wait_for_timeout(3000)

        print(f"Captured {len(api_calls)} API calls so far:")
        for call in api_calls:
            print(f"  {call['url']}")
            if call['body']:
                print(f"    Body: {call['body'][:200]}")

        # Try to find and click "Print Teacher Details" button
        print("\n=== Looking for Print Teacher Details button ===")
        buttons = await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button, a, span'));
            return btns.filter(b => {
                const text = b.textContent.trim().toLowerCase();
                return text.includes('print') || text.includes('details') || text.includes('view');
            }).map(b => ({
                tag: b.tagName,
                text: b.textContent.trim().substring(0, 50),
                class: b.className,
            }));
        }""")
        print(f"Found {len(buttons)} potential buttons:")
        for btn in buttons:
            print(f"  {btn['tag']}: '{btn['text']}' (class={btn['class']})")

        # Try clicking the first "Print" or "Details" button
        for btn in buttons:
            if 'print' in btn['text'].lower() or 'details' in btn['text'].lower():
                print(f"\nClicking: {btn['text']}")
                try:
                    # Clear previous calls
                    api_calls.clear()
                    
                    # Click the button
                    await page.evaluate(f"""() => {{
                        const btns = Array.from(document.querySelectorAll('button, a, span'));
                        const btn = btns.find(b => b.textContent.trim().toLowerCase().includes('{btn['text'].lower().split()[0]}'));
                        if (btn) btn.click();
                    }}""")
                    
                    # Wait for new API calls
                    await page.wait_for_timeout(5000)
                    
                    print(f"Captured {len(api_calls)} API calls after click:")
                    for call in api_calls:
                        print(f"  {call['url']}")
                        if call['body']:
                            print(f"    Body: {call['body'][:300]}")
                    
                    # Check if a new tab opened
                    pages = context.pages
                    if len(pages) > 1:
                        print(f"\nNew tab opened! Total pages: {len(pages)}")
                        new_page = pages[-1]
                        content = await new_page.content()
                        print(f"New tab content length: {len(content)}")
                        # Look for education-related content
                        if 'education' in content.lower() or 'qualification' in content.lower() or 'degree' in content.lower():
                            print("  ✅ Education-related content found in new tab!")
                            # Extract text content
                            text = await new_page.evaluate("() => document.body.innerText")
                            print(f"  Text content (first 1000 chars): {text[:1000]}")
                    
                    break
                except Exception as e:
                    print(f"  Error clicking: {e}")

        await browser.close()

asyncio.run(main())
