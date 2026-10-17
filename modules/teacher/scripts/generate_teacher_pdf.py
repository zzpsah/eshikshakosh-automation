#!/usr/bin/env python3
"""Generate a 7-page PDF report for a specific teacher from e-ShikshaKosh.

Usage:
    python3 generate_teacher_pdf.py --teacher-id 24230196 --school Sahaspur

Output:
    ~/exports/Teacher_Report_<name>_<id>.pdf
"""
import asyncio
import os
import sys
import re
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from fpdf import FPDF

SCHOOLS = {
    "Sahaspur": {
        "udise": "10130106304",
        "username_key": "ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_USERNAME",
        "password_key": "ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_PASSWORD",
    },
    "Tetahali": {
        "udise": "10160203806",
        "username_key": "ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_USERNAME",
        "password_key": "ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_PASSWORD",
    },
}

BASE_URL = "https://eshikshakosh.bihar.gov.in:8443"
LOGIN_URL = "https://eshikshakosh.bihar.gov.in/login"
PORTAL_URL = "https://eshikshakosh.bihar.gov.in/"


def get_credentials(school_name: str) -> tuple[str, str]:
    """Fetch credentials from Bitwarden via bws-hermes."""
    import subprocess
    school = SCHOOLS[school_name]
    username = subprocess.check_output(
        ["bws-hermes", "secret", "get", school["username_key"]],
        text=True
    ).strip()
    password = subprocess.check_output(
        ["bws-hermes", "secret", "get", school["password_key"]],
        text=True
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
    
    def field_row(self, label: str, value: str, indent: int = 0):
        """Add a label-value row."""
        self.set_font("Helvetica", "B", 9)
        x_start = self.l_margin + indent
        self.set_x(x_start)
        self.cell(60, 6, f"{label}:")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, str(value) if value else "-", new_x="LMARGIN", new_y="NEXT")
    
    def field_table(self, data: dict, fields: list[tuple[str, str]], cols: int = 2):
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
                self.field_row(label, value)
        self.ln(1)


async def extract_teacher_details(teacher_id: str, school_name: str) -> dict:
    """Login and extract all teacher details from all tabs."""
    from playwright.async_api import async_playwright
    
    username, password = get_credentials(school_name)
    school = SCHOOLS[school_name]
    
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
        
        # Click School Login
        try:
            await page.click("text=School Login", timeout=5000)
        except:
            pass
        
        await page.fill("input[formcontrolname='username']", username)
        await page.fill("input[formcontrolname='password']", password)
        
        # Captcha handling
        try:
            captcha_text = await page.text_content("captcha-info, .captcha-text, [class*='captcha']")
            if captcha_text:
                match = re.search(r'(\d+)\s*[\+\-\*]\s*(\d+)', captcha_text)
                if match:
                    a, b = int(match.group(1)), int(match.group(2))
                    op = re.search(r'[\+\-\*]', captcha_text)
                    if op:
                        op = op.group()
                        ans = a + b if op == '+' else a - b if op == '-' else a * b
                        await page.fill("input[formcontrolname='captcha']", str(ans))
                        print(f"Captcha solved: {a} {op} {b} = {ans}")
        except Exception as e:
            print(f"Captcha: {e}")
        
        await page.click("button[type='submit']")
        await page.wait_for_timeout(3000)
        
        # Verify login
        if "dashboard" in page.url.lower() or "home" in page.url.lower():
            print("Login successful!")
        else:
            print(f"Login may have failed. URL: {page.url}")
            # Continue anyway
        
        # Step 2: Navigate to teacher detail page
        detail_url = f"{BASE_URL}/teacher/viewTeacher?teacherId={teacher_id}"
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
                details[f"{tab_key}_error"] = str(e)
        
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
    lines = text.split("\n")
    current = {}
    for line in lines:
        if "Service History" in line or "e-ShikshaKosh" in line:
            continue
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
        if "Educational" in line or "e-ShikshaKosh" in line:
            continue
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
        if "Professional" in line or "e-ShikshaKosh" in line:
            continue
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
        if "Training" in line or "e-ShikshaKosh" in line:
            continue
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
