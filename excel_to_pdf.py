#!/usr/bin/env python3
"""Generate 7-page PDF report for Nitilata Kumari from extracted Excel data.

Usage:
    python3 excel_to_pdf.py --input <excel_path> --teacher-name "NITILATA KUMARI"
"""
import sys
from pathlib import Path
from datetime import datetime

import openpyxl
from fpdf import FPDF

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import re

# Register Unicode fonts (supports Hindi/Devanagari)
FONT_REGULAR = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"


class TeacherPDF(FPDF):
    """A4 Portrait PDF with header/footer for teacher reports."""

    def __init__(self, teacher_name: str, school_name: str):
        super().__init__("P", "mm", "A4")
        # Register Unicode fonts
        self.add_font("Noto", "", FONT_REGULAR, uni=True)
        self.add_font("Noto", "B", FONT_BOLD, uni=True)
        self.set_font("Noto", "", 9)
        self.teacher_name = teacher_name
        self.school_name = school_name
        self.set_auto_page_break(auto=True, margin=20)
    
    def header(self):
        self.set_font("Noto", "B", 10)
        self.cell(0, 6, "e-ShikshaKosh - Bihar Education Project Council", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Noto", "", 8)
        self.cell(0, 5, f"Teacher Profile Report | Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
    
    def footer(self):
        self.set_y(-15)
        self.set_font("Noto", "B", 8)
        self.set_text_color(128)
        self.cell(0, 10, f"Page {self.page_no()} of {{nb}} | {self.teacher_name} - {self.school_name}", align="C")
    
    def section_title(self, title: str):
        self.set_font("Noto", "B", 12)
        self.set_text_color(30, 80, 162)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
    
    def field_row(self, label: str, value: str, col_width: int = 50):
        self.set_font("Noto", "B", 9)
        self.cell(col_width, 6, f"{label}:")
        self.set_font("Noto", "", 9)
        self.cell(0, 6, str(value) if value else "-", new_x="LMARGIN", new_y="NEXT")
    
    def field_table(self, data: dict, fields: list, cols: int = 2):
        rows = []
        for key, label in fields:
            val = data.get(key, "")
            if val is None:
                val = ""
            rows.append((label, str(val) if val else "-"))
        
        if cols == 2:
            half = (len(rows) + 1) // 2
            for i in range(half):
                self.set_font("Noto", "B", 8)
                self.cell(48, 5.5, rows[i][0][:28])
                self.set_font("Noto", "", 8)
                self.cell(48, 5.5, str(rows[i][1])[:35])
                if i + half < len(rows):
                    self.set_font("Noto", "B", 8)
                    self.cell(48, 5.5, rows[i + half][0][:28])
                    self.set_font("Noto", "", 8)
                    self.cell(48, 5.5, str(rows[i + half][1])[:35])
                self.ln()
        else:
            for label, value in rows:
                self.field_row(label, value)
        self.ln(1)


def generate_pdf(excel_path: str, teacher_name: str, output_path: str):
    """Generate 7-page PDF from extracted Excel data."""
    wb = openpyxl.load_workbook(excel_path)
    
    # Find teacher in Registration Info sheet
    reg_sheet = wb['Registration Info']
    reg_headers = [cell.value for cell in reg_sheet[1]]
    teacher_row = None
    teacher_data = {}
    for row in range(2, reg_sheet.max_row + 1):
        name = reg_sheet.cell(row, reg_headers.index('teacherName') + 1).value or ''
        if teacher_name.lower() in name.lower():
            teacher_row = row
            for col, header in enumerate(reg_headers, 1):
                teacher_data[header] = reg_sheet.cell(row, col).value
            break
    
    if not teacher_row:
        print(f"ERROR: Teacher '{teacher_name}' not found in Registration Info")
        return
    
    print(f"Found: {teacher_data.get('teacherName')} (ID: {teacher_data.get('tId')})")
    
    school_name = teacher_data.get('schoolName', 'UCHCHA MADHYAMIK VIDYALAYA SAHASPUR')
    
    pdf = TeacherPDF(teacher_name, school_name)
    
    # Page 1: Registration Info
    pdf.add_page()
    pdf.section_title("1. Registration Information")
    pdf.set_font("Noto", "B", 11)
    pdf.cell(0, 7, f"Teacher Name: {teacher_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"School: {school_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Teacher ID: {teacher_data.get('tId', '-')}", new_x="LMARGIN", new_y="NEXT")
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
    pdf.field_table(teacher_data, fields, cols=2)
    
    # Page 2: Service History
    pdf.add_page()
    pdf.section_title("2. Service History")
    sh_sheet = wb['Service History']
    sh_headers = [cell.value for cell in sh_sheet[1]]
    sh_records = []
    for row in range(2, sh_sheet.max_row + 1):
        record = {}
        for col, header in enumerate(sh_headers, 1):
            val = sh_sheet.cell(row, col).value
            record[header] = val
        # Filter by teacher
        tname = record.get('teacherName', '') or ''
        tid = record.get('teacherId', '') or record.get('tId', '')
        if teacher_name.lower() in str(tname).lower() or str(teacher_data.get('tId', '')) in str(tid):
            sh_records.append(record)
    
    if sh_records:
        for i, record in enumerate(sh_records, 1):
            pdf.set_font("Noto", "B", 9)
            pdf.cell(0, 6, f"  Entry {i}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Noto", "", 8)
            for k, v in record.items():
                if v is not None and str(v).strip():
                    pdf.cell(50, 5, f"  {k}:")
                    pdf.cell(0, 5, str(v)[:60], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
    else:
        pdf.set_font("Noto", "B", 10)
        pdf.cell(0, 8, "No service history records found.", new_x="LMARGIN", new_y="NEXT")
    
    # Page 3: Educational Info
    pdf.add_page()
    pdf.section_title("3. Educational Information")
    edu_sheet = wb['Education']
    edu_headers = [cell.value for cell in edu_sheet[1]]
    for row in range(2, edu_sheet.max_row + 1):
        record = {}
        for col, header in enumerate(edu_headers, 1):
            record[header] = edu_sheet.cell(row, col).value
        tname = str(record.get('Teacher Name', '') or '')
        if teacher_name.lower() in tname.lower():
            pdf.set_font("Noto", "", 9)
            for k, v in record.items():
                if v is not None and str(v).strip():
                    pdf.cell(50, 5.5, f"  {k}:")
                    pdf.cell(0, 5.5, str(v)[:80], new_x="LMARGIN", new_y="NEXT")
            break
    else:
        pdf.set_font("Noto", "B", 10)
        pdf.cell(0, 8, "No educational records found.", new_x="LMARGIN", new_y="NEXT")
    
    # Page 4: Professional Info
    pdf.add_page()
    pdf.section_title("4. Professional Information")
    prof_sheet = wb['Professional']
    prof_headers = [cell.value for cell in prof_sheet[1]]
    for row in range(2, prof_sheet.max_row + 1):
        record = {}
        for col, header in enumerate(prof_headers, 1):
            record[header] = prof_sheet.cell(row, col).value
        tname = str(record.get('Teacher Name', '') or '')
        if teacher_name.lower() in tname.lower():
            pdf.set_font("Noto", "", 9)
            for k, v in record.items():
                if v is not None and str(v).strip():
                    pdf.cell(50, 5.5, f"  {k}:")
                    pdf.cell(0, 5.5, str(v)[:80], new_x="LMARGIN", new_y="NEXT")
            break
    else:
        pdf.set_font("Noto", "B", 10)
        pdf.cell(0, 8, "No professional records found.", new_x="LMARGIN", new_y="NEXT")
    
    # Page 5: Training & Language Info
    pdf.add_page()
    pdf.section_title("5. Training & Language Information")
    train_sheet = wb['Training']
    train_headers = [cell.value for cell in train_sheet[1]]
    for row in range(2, train_sheet.max_row + 1):
        record = {}
        for col, header in enumerate(train_headers, 1):
            record[header] = train_sheet.cell(row, col).value
        tname = str(record.get('Teacher Name', '') or '')
        if teacher_name.lower() in tname.lower():
            pdf.set_font("Noto", "", 9)
            for k, v in record.items():
                if v is not None and str(v).strip():
                    pdf.cell(50, 5.5, f"  {k}:")
                    pdf.cell(0, 5.5, str(v)[:80], new_x="LMARGIN", new_y="NEXT")
            break
    else:
        pdf.set_font("Noto", "B", 10)
        pdf.cell(0, 8, "No training records found.", new_x="LMARGIN", new_y="NEXT")
    
    # Page 6: Other Details
    pdf.add_page()
    pdf.section_title("6. Other Details")
    other_sheet = wb['Other Info']
    other_headers = [cell.value for cell in other_sheet[1]]
    for row in range(2, other_sheet.max_row + 1):
        record = {}
        for col, header in enumerate(other_headers, 1):
            record[header] = other_sheet.cell(row, col).value
        tname = str(record.get('Teacher Name', '') or '')
        if teacher_name.lower() in tname.lower():
            pdf.set_font("Noto", "", 9)
            for k, v in record.items():
                if v is not None and str(v).strip():
                    pdf.cell(50, 5.5, f"  {k}:")
                    pdf.cell(0, 5.5, str(v)[:80], new_x="LMARGIN", new_y="NEXT")
            break
    else:
        pdf.set_font("Noto", "B", 10)
        pdf.cell(0, 8, "No additional details found.", new_x="LMARGIN", new_y="NEXT")
    
    # Page 7: Summary & Declaration
    pdf.add_page()
    pdf.section_title("7. Summary & Declaration")
    pdf.set_font("Noto", "", 10)
    summary_text = f"""
This is a system-generated report from the e-ShikshaKosh portal, Bihar Education Project Council.

Teacher: {teacher_name}
School: {school_name}
Teacher ID: {teacher_data.get('tId', '-')}

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


if __name__ == "__main__":
    excel_path = "/home/prashant/exports/Teacher_Details_UCHCHA_MADHYAMIK_VIDYALAYA_SAHASPUR_20261017_093550.xlsx"
    teacher_name = "NITILATA KUMARI"
    output_path = f"/home/prashant/exports/Teacher_Report_{teacher_name.replace(' ', '_')}_24230196.pdf"
    generate_pdf(excel_path, teacher_name, output_path)
