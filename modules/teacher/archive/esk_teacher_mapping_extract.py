#!/usr/bin/env python3
"""Extract encoded field mappings from teacher page dropdowns."""
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

        # Login
        await page.goto("https://eshikshakosh.bihar.gov.in", wait_until="networkidle", timeout=90000)
        udise_input = page.locator("input[placeholder='11-Digit UDISE Code']")
        await udise_input.fill(school_id)
        await page.fill("input[placeholder='Password']", password)
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

        # Extract all dropdown options from the page
        mappings = await page.evaluate("""() => {
            const result = {};
            // Find all select elements
            const selects = document.querySelectorAll('select');
            selects.forEach((sel, idx) => {
                const name = sel.name || sel.id || `select_${idx}`;
                const options = Array.from(sel.options).map(o => ({
                    value: o.value,
                    text: o.text.trim(),
                }));
                if (options.length > 0) {
                    result[name] = options;
                }
            });
            return result;
        }""")

        print("=== Dropdown mappings ===")
        for name, options in mappings.items():
            print(f"\n{name}:")
            for opt in options:
                print(f"  {opt['value']}: {opt['text']}")

        # Also try to find Vue/React data in page source
        vue_data = await page.evaluate("""() => {
            // Try to find Vue data
            const app = document.querySelector('#app');
            if (app && app.__vue__) {
                return JSON.stringify(app.__vue__.$data);
            }
            // Try to find global data
            if (window.__INITIAL_STATE__) {
                return JSON.stringify(window.__INITIAL_STATE__);
            }
            return null;
        }""")
        if vue_data:
            print(f"\n=== Vue/Initial data ===")
            print(vue_data[:2000])

        await browser.close()

asyncio.run(main())
