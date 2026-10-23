#!/usr/bin/env python3
"""Generate a 7-page PDF report for a specific teacher from e-ShikshaKosh.

Uses the proven login pattern from esk_teacher_detail_extract.py.

Usage:
    python3 generate_teacher_pdf.py --teacher-id 24230196 --school Sahaspur

Output:
    ~/exports/Teacher_Report_<name>_<id>.pdf
"""
import asyncio
import os
import sys
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from fpdf import FPDF

BASE = "https://eshikshakosh.bihar.gov.in:8443"
LOGIN_URL = "https://eshikshakosh.bihar.gov.in/login"

SECRET_IDS = {
    "Sahaspur": {
        "username": "8f62c170-944a-4bb7-a6bd-b4d70084fea8",
        "password": "4b7b811e-833e-45df-9993-b4d70084ff5a",
    },
    "Tetahali": {
        "username": None,  # Look up dynamically
        "password": None,
    },
}

SCHOOL_NAMES = {
    "Sahaspur": "UCHCHA MADHYAMIK VIDYALAYA SAHASPUR",
    "Tetahali": "UCHCH MADHYAMIK VIDYALAY, TETAHALI",
}


def get_credentials(school_name: str) -> tuple[str, str]:
    """Fetch credentials from Bitwarden via bws-hermes."""
    ids = SECRET_IDS[school_name]
    
    if ids["username"] and ids["password"]:
        # Use hardcoded IDs for Sahaspur
        uid = subprocess.check_output(
            ["bws-hermes", "secret", "get", ids["username"]],
            text=True
        ).strip()
        pwd = subprocess.check_output(
            ["bws-hermes", "secret", "get", ids["password"]],
            text=True
        ).strip()
        return uid, pwd
    else:
        # Dynamic lookup for other schools
        result = subprocess.check_output(
            ["bws-hermes", "secret", "list"],
            text=True
        )
        secrets = json.loads(result)
        username_key = f"ESHIKSHAKOSH_UMV_{school_name.upper()}_SCHOOL_USERNAME"
        password_key = f"ESHIKSHAKOSH_UMV_{school_name.upper()}_SCHOOL_PASSWORD"
        uid = pwd = ""
        for s in secrets:
            if s.get("key") == username_key:
                uid = s["id"]
            elif s.get("key") == password_key:
                pwd = s["id"]
        username = subprocess.check_output(
            ["bws-hermes", "secret", "get", uid], text=True
        ).strip()
        password = subprocess.check_output(
            ["bws-hermes", "secret", "get", pwd], text=True
        ).strip()
        return username, password


class TeacherPDF(FPDF):
    """A4 Portrait PDF with header/footer for teacher reports."""
    
    def __init__(self, teacher_name: str, school_name: str):
        super().__init__("P", "mm", "A4")
        self.teacher_name = teacher_name
        self.school_name = school_name
        self.set_auto_page_break(auto=True, margin=20)
    
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 6, "e-ShikshaKosh - Bihar Education Project Council", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 5, f"Teacher Profile Report | Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
    
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f"Page {self.page_no()} of {{nb}} | {self.teacher_name} - {self.school_name}", align="C")
    
    def section_title(self, title: str):
        """Add a section heading."""
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(30, 80, 162)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
    
    def field_table(self, data: dict, fields: list, cols: int = 2):
        """Add fields in a multi-column table layout."""
        rows = []
        for key, label in fields:
            val = data.get(key, "")
            if val is None:
                val = ""
            rows.append((label, str(val) if val else "-"))
        
        if cols == 2:
            half = (len(rows) + 1) // 2
            for i in range(half):
                self.set_font("Helvetica", "B", 8)
                self.cell(48, 5.5, rows[i][0][:28])
                self.set_font("Helvetica", "", 8)
                self.cell(48, 5.5, str(rows[i][1])[:35])
                if i + half < len(rows):
                    self.set_font("Helvetica", "B", 8)
                    self.cell(48, 5.5, rows[i + half][0][:28])
                    self.set_font("Helvetica", "", 8)
                    self.cell(48, 5.5, str(rows[i + half][1])[:35])
                self.ln()
        else:
            for label, value in rows:
                self.set_font("Helvetica", "B", 8)
                self.cell(50, 5.5, f"{label}:")
                self.set_font("Helvetica", "", 8)
                self.cell(0, 5.5, str(value)[:80], new_x="LMARGIN", new_y="NEXT")
        self.ln(1)


async def extract_teacher_details(teacher_id: str, school_name: str) -> dict:
    """Login and extract all teacher details from all tabs."""
    from playwright.async_api import async_playwright
    
    username, password = get_credentials(school_name)
    
    details = {
        "teacher_id": teacher_id,
        "school": school_name,
        "registration": {},
        "service_history": [],
        "education": [],
        "professional": [],
        "training": [],
        "other": {},
    }
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True
        )
        page = await context.new_page()
        
        # Step 1: Login
        print("Logging in...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)
        
        # Click School Login radio using check() — works with Angular
        try:
            await page.check('#radio2', timeout=5000)
            print("Selected School Login via check()")
        except:
            # Fallback: JS click
            await page.evaluate("document.querySelector('#radio2').click()")
            print("Selected School Login via JS click")
        await page.wait_for_timeout(1000)
        
        # Fill credentials
        await page.wait_for_selector("input[formcontrolname='userId']", timeout=15000)
        await page.fill("input[formcontrolname='userId']", username)
        await page.fill("input[formcontrolname='password']", password)
        
        # Captcha handling — screenshot lo, user se solve karwao
        captcha_text = await page.inner_text('.capcha__head')
        print(f"Captcha text: {captcha_text}")
        
        # Screenshot of captcha area
        captcha_el = await page.query_selector('.capcha__head')
        if captcha_el:
            await captcha_el.screenshot(path='/tmp/captcha.png')
            print("Captcha screenshot saved: /tmp/captcha.png")
        
        # Try auto-solve first
        m = re.search(r'(\d+)\s*([+\-*])\s*(\d+)', captcha_text)
        if m:
            a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
            ans = a + b if op == '+' else a - b if op == '-' else a * b
            await page.fill("input[placeholder='Enter User Captcha']", str(ans))
            print(f"Auto-solved captcha: {a} {op} {b} = {ans}")
        else:
            # Manual input
            ans = input("Enter captcha answer (or press Enter to skip): ").strip()
            if ans:
                await page.fill("input[placeholder='Enter User Captcha']", ans)
        
        # Submit login
        await page.click('input.submit__btn')
        await page.wait_for_timeout(5000)
        
        # Check login success by URL redirect
        current_url = page.url
        print(f"URL after login: {current_url}")
        
        if "login" in current_url.lower():
            # Still on login page — check for error
            error_text = await page.evaluate("""() => {
                const errs = document.querySelectorAll('[class*=error], [class*=alert], [class*=invalid]');
                return Array.from(errs).map(e => e.textContent.trim()).filter(t => t.length > 0).join(' | ');
            }""")
            print(f"Login errors: {error_text}")
            raise RuntimeError(f"Login failed — still on login page. Errors: {error_text}")
        
        print("Login successful!")
        
        # Step 2: Navigate to teacher detail page
        detail_url = f"{BASE}/Application/teacher/registration/viewTeacher?teacherId={teacher_id}"
        print(f"Navigating to: {detail_url}")
        await page.goto(detail_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)
        
        # Step 3: Extract Registration Info (default tab)
        print("Extracting Registration Info...")
        reg_text = await page.evaluate("() => document.body.innerText")
        details["registration"] = parse_registration(reg_text)
        
        # Step 4: Click through tabs and extract
        tabs = [
            ("Service History", "service"),
            ("Educational Info", "education"),
            ("Professional Info", "professional"),
            ("Training & Language Info", "training"),
            ("Other Details", "other"),
        ]
        
        for tab_name, tab_key in tabs:
            print(f"Extracting {tab_name}...")
            try:
                # Click the tab
                await page.click(f"text={tab_name}", timeout=5000)
                await page.wait_for_timeout(2000)
                
                tab_text = await page.evaluate("() => document.body.innerText")
                
                if tab_key == "service":
                    details["service_history"] = parse_service_history(tab_text)
                elif tab_key == "education":
                    details["education"] = parse_education(tab_text)
                elif tab_key == "professional":
                    details["professional"] = parse_professional(tab_text)
                elif tab_key == "training":
                    details["training"] = parse_training(tab_text)
                elif tab_key == "other":
                    details["other"] = parse_other(tab_text)
                    
            except Exception as e:
                print(f"  Tab '{tab_name}' error: {e}")
        
        await browser.close()
    
    return details


def parse_registration(text: str) -> dict:
    """Parse registration info from page text."""
    fields = {}
    patterns = {
        "teacherName": r"Teacher Name[:\s]+(.+)",
        "teacherLoginCode": r"Temp Login ID[:\s]+(.+)",
        "gender": r"Gender[:\s]+(.+)",
        "DOB": r"Date of Birth[:\s]+(.+)",
        "mobile": r"Mobile[:\s]+(.+)",
        "teacherEmail": r"Email[:\s]+(.+)",
        "aadhaarNo": r"Aadhaar[:\s]+(.+)",
        "panNo": r"PAN[:\s]+(.+)",
        "pranNo": r"PRAN[:\s]+(.+)",
        "gpfNo": r"GPF[:\s]+(.+)",
        "uanNo": r"UAN[:\s]+(.+)",
        "fatherName": r"Father Name[:\s]+(.+)",
        "motherName": r"Mother Name[:\s]+(.+)",
        "socialCategory": r"Social Category[:\s]+(.+)",
        "maritalStatus": r"Marital Status[:\s]+(.+)",
        "teacherTitle": r"Teacher Title[:\s]+(.+)",
        "natureOfAppointmt": r"Nature of Appointment[:\s]+(.+)",
        "serviceJoiningDt": r"Service Joining Date[:\s]+(.+)",
        "joiningCurrentSchoolDt": r"Joining Current School Date[:\s]+(.+)",
        "schoolName": r"School Name[:\s]+(.+)",
        "schoolUdiseCode": r"School UDISE Code[:\s]+(.+)",
        "appointedSubject": r"Appointed Subject[:\s]+(.+)",
        "employeeCode": r"Employee Code[:\s]+(.+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            fields[key] = match.group(1).strip()
    return fields


def parse_service_history(text: str) -> list:
    """Parse service history table."""
    entries = []
    current = {}
    for line in text.split("\n"):
        if ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].strip():
                if current:
                    entries.append(current)
                current = {parts[0].strip(): parts[1].strip()}
    if current:
        entries.append(current)
    return entries


def parse_education(text: str) -> list:
    """Parse education details."""
    entries = []
    current = {}
    for line in text.split("\n"):
        if ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].strip():
                if current:
                    entries.append(current)
                current = {parts[0].strip(): parts[1].strip()}
    if current:
        entries.append(current)
    return entries


def parse_professional(text: str) -> list:
    """Parse professional info."""
    entries = []
    current = {}
    for line in text.split("\n"):
        if ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].strip():
                if current:
                    entries.append(current)
                current = {parts[0].strip(): parts[1].strip()}
    if current:
        entries.append(current)
    return entries


def parse_training(text: str) -> list:
    """Parse training info."""
    entries = []
    current = {}
    for line in text.split("\n"):
        if ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].strip():
                if current:
                    entries.append(current)
                current = {parts[0].strip(): parts[1].strip()}
    if current:
        entries.append(current)
    return entries


def parse_other(text: str) -> dict:
    """Parse other details."""
    fields = {}
    for line in text.split("\n"):
        if ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].strip():
                fields[parts[0].strip()] = parts[1].strip()
    return fields


def generate_pdf(details: dict, output_path: str):
    """Generate 7-page PDF report."""
    reg = details.get("registration", {})
    teacher_name = reg.get("teacherName", "Unknown")
    school_name = reg.get("schoolName", details.get("school", ""))
    
    pdf = TeacherPDF(teacher_name, school_name)
    
    # Page 1: Registration Info
    pdf.add_page()
    pdf.section_title("1. Registration Information")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, f"Teacher Name: {teacher_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"School: {school_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Teacher ID: {details['teacher_id']}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    
    fields = [
        ("teacherLoginCode", "Temp Login ID"),
        ("gender", "Gender"),
        ("DOB", "Date of Birth"),
        ("teacherTitle", "Teacher Title"),
        ("natureOfAppointmt", "Nature of Appointment"),
        ("serviceJoiningDt", "Service Joining Date"),
        ("joiningCurrentSchoolDt", "Joining Current School Date"),
        ("mobile", "Mobile"),
        ("teacherEmail", "Email"),
        ("aadhaarNo", "Aadhaar Number"),
        ("panNo", "PAN Number"),
        ("pranNo", "PRAN Number"),
        ("gpfNo", "GPF Number"),
        ("uanNo", "UAN Number"),
        ("fatherName", "Father Name"),
        ("motherName", "Mother Name"),
        ("socialCategory", "Social Category"),
        ("maritalStatus", "Marital Status"),
        ("employeeCode", "Employee Code"),
    ]
    pdf.field_table(reg, fields, cols=2)
    
    # Page 2: Service History
    pdf.add_page()
    pdf.section_title("2. Service History")
    service = details.get("service_history", [])
    if service:
        for i, entry in enumerate(service, 1):
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, f"  Entry {i}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            for k, v in entry.items():
                pdf.cell(50, 5, f"  {k}:")
                pdf.cell(0, 5, str(v)[:60], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "No service history records found.", new_x="LMARGIN", new_y="NEXT")
    
    # Page 3: Educational Info
    pdf.add_page()
    pdf.section_title("3. Educational Information")
    education = details.get("education", [])
    if education:
        for i, entry in enumerate(education, 1):
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, f"  Qualification {i}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            for k, v in entry.items():
                pdf.cell(50, 5, f"  {k}:")
                pdf.cell(0, 5, str(v)[:60], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "No educational records found.", new_x="LMARGIN", new_y="NEXT")
    
    # Page 4: Professional Info
    pdf.add_page()
    pdf.section_title("4. Professional Information")
    professional = details.get("professional", [])
    if professional:
        for i, entry in enumerate(professional, 1):
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, f"  Record {i}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            for k, v in entry.items():
                pdf.cell(50, 5, f"  {k}:")
                pdf.cell(0, 5, str(v)[:60], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "No professional records found.", new_x="LMARGIN", new_y="NEXT")
    
    # Page 5: Training & Language Info
    pdf.add_page()
    pdf.section_title("5. Training & Language Information")
    training = details.get("training", [])
    if training:
        for i, entry in enumerate(training, 1):
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, f"  Training {i}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            for k, v in entry.items():
                pdf.cell(50, 5, f"  {k}:")
                pdf.cell(0, 5, str(v)[:60], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "No training records found.", new_x="LMARGIN", new_y="NEXT")
    
    # Page 6: Other Details
    pdf.add_page()
    pdf.section_title("6. Other Details")
    other = details.get("other", {})
    if other:
        pdf.set_font("Helvetica", "", 9)
        for k, v in other.items():
            pdf.cell(50, 5.5, f"  {k}:")
            pdf.cell(0, 5.5, str(v)[:80], new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "No additional details found.", new_x="LMARGIN", new_y="NEXT")
    
    # Page 7: Summary & Declaration
    pdf.add_page()
    pdf.section_title("7. Summary & Declaration")
    pdf.set_font("Helvetica", "", 10)
    summary_text = f"""
This is a system-generated report from the e-ShikshaKosh portal, Bihar Education Project Council.

Teacher: {teacher_name}
School: {school_name}
Teacher ID: {details['teacher_id']}

This document contains the following sections:
  1. Registration Information
  2. Service History
  3. Educational Information
  4. Professional Information
  5. Training & Language Information
  6. Other Details

This report is generated for official use only. The data is fetched directly
from the e-ShikshaKosh portal and is subject to portal updates.

Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
"""
    pdf.multi_cell(0, 6, summary_text)
    
    pdf.output(output_path)
    print(f"\nPDF generated: {output_path}")


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-id", required=True)
    parser.add_argument("--school", default="Sahaspur")
    args = parser.parse_args()
    
    print(f"Extracting teacher {args.teacher_id} from {args.school}...")
    details = await extract_teacher_details(args.teacher_id, args.school)
    
    # Generate output filename
    reg = details.get("registration", {})
    teacher_name = reg.get("teacherName", "Unknown").replace(" ", "_")
    output = str(Path.home() / "exports" / f"Teacher_Report_{teacher_name}_{args.teacher_id}.pdf")
    
    generate_pdf(details, output)
    return output


if __name__ == "__main__":
    result = asyncio.run(main())
