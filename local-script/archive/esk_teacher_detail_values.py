#!/usr/bin/env python3
"""Extract actual field values from a teacher detail page by teacher ID."""
import asyncio
import json
import os
import sys
from playwright.async_api import async_playwright

def get_env(key):
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Missing env var: {key}")
    return val

async def main():
    school_id = get_env("ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_USERNAME")
    password = get_env("ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_PASSWORD")
    teacher_id = sys.argv[1] if len(sys.argv) > 1 else "2020000001"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        # Login
        await page.goto("https://eshikshakosh.bihar.gov.in", wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(3000)
        udise_input = page.locator("input[placeholder='11-Digit UDISE Code']")
        await udise_input.wait_for(state="visible", timeout=30000)
        await udise_input.fill(school_id)
        pwd_input = page.locator("input[placeholder='Enter Password']")
        await pwd_input.fill(password)

        # Captcha
        captcha_text = await page.evaluate("""() => {
            const img = document.querySelector('img[src*="captcha"], img[alt*="captcha"], img[alt*="Captcha"]');
            if (img) return img.src;
            const canvas = document.querySelector('canvas');
            if (canvas) return canvas.toDataURL();
            return null;
        }""")
        if captcha_text and captcha_text.startswith("data:"):
            import base64
            captcha_b64 = captcha_text.split(",")[1]
            captcha_path = "/tmp/captcha.png"
            with open(captcha_path, "wb") as f:
                f.write(base64.bdecode(captcha_b64))
            print(f"Captcha saved to {captcha_path}")
            # Try to solve captcha
            from PIL import Image
            import pytesseract
            img = Image.open(captcha_path)
            captcha_solution = pytesseract.image_to_string(img, config="--psm 7 -c tessedit_char_whitelist=0123456789").strip()
            print(f"Captcha solution: {captcha_solution}")
            captcha_input = page.locator("input[placeholder*='captcha' i], input[placeholder*='Captcha' i], input[name*='captcha' i]")
            await captcha_input.fill(captcha_solution)

        # Click login
        login_btn = page.locator("button:has-text('Login'), input[type='submit'][value*='Login' i]")
        await login_btn.click()
        await page.wait_for_timeout(5000)

        # Navigate to teacher detail page
        await page.goto(
            f"https://eshikshakosh.bihar.gov.in/Application/teacher/registration/viewTeacher?teacherId={teacher_id}",
            wait_until="networkidle", timeout=35000,
        )
        await page.wait_for_timeout(5000)

        # Extract all form field values
        fields = await page.evaluate("""() => {
            const result = {};
            // Get all input fields
            const inputs = document.querySelectorAll('input, select, textarea');
            inputs.forEach(el => {
                const name = el.name || el.id || el.placeholder || '';
                if (name) {
                    if (el.tagName === 'SELECT') {
                        const selected = el.options[el.selectedIndex];
                        result[name] = {value: el.value, text: selected ? selected.text : ''};
                    } else if (el.type === 'checkbox') {
                        result[name] = el.checked;
                    } else if (el.type === 'radio') {
                        if (el.checked) result[name] = el.value;
                    } else {
                        result[name] = el.value;
                    }
                }
            });
            return result;
        }""")

        print(f"\nTeacher ID: {teacher_id}")
        print(f"Fields extracted: {len(fields)}")
        print(json.dumps(fields, indent=2, ensure_ascii=False))

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
