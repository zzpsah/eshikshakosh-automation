================================================================================
  ESHIKSHAKOSH OTR REPORT GENERATOR — LOCAL SCRIPT
  ==================================================
  School: UCHCH MADHYAMIK VIDYALAY, TETAHALI
  UDISE: 10160203806 | School ID: 42645 | Siwan, Bihar
================================================================================

WHAT THIS DOES
--------------
Logs into e-Shikshakosh Bihar portal → fetches all 220 students →
pulls Mother Name, Bank Account No, IFSC, Bank Name, OTR Number,
OTR Status, unmasked Aadhaar → exports a clean Excel file.

YOU NEED NOTHING ELSE. No token. No browser. Just run the script.


================================================================================
  FILES IN THIS FOLDER
================================================================================

Location: C:\Users\Admin\Eshikshakosh_OTR_Report\

  FILE                        SIZE      WHAT IT IS
  --------------------------  --------  ---------------------------
  esk_otr_api.py              18,342    THE SCRIPT (run this)
  eshikshakosh.conf           73        Config template (edit before use)
  READ_ME_FIRST.txt           9,886     This file — full documentation
  Student_OTR_Report_2026-27.xlsx  43,803  THE OUTPUT Excel file
                                    (generated after run)


================================================================================
  HOW TO RUN — 4 WAYS
================================================================================

WAY 1 — Direct command with interactive password prompt (RECOMMENDED)
----------------------------------------------------------------------
Open Command Prompt and run:

  cd C:\Users\Admin\Eshikshakosh_OTR_Report

  C:\Users\Admin\AppData\Local\hermes\hermes-agent\venv\Scripts\python
    esk_otr_api.py --udise 10160203806

  It will ask:
    Password: [type your password — invisible]

  Then it will show the captcha and either solve it automatically
  OR ask you to type the answer.


WAY 2 — Direct command with password in command line
------------------------------------------------------
  cd C:\Users\Admin\Eshikshakosh_OTR_Report

  C:\Users\Admin\AppData\Local\hermes\hermes-agent\venv\Scripts\python
    esk_otr_api.py --udise 10160203806 --password "your-password-here"


WAY 3 — Using config file
--------------------------
Edit eshikshakosh.conf first (remove the # from password line,
replace "your-password-here" with your actual password):

  [eshikshakosh]
  udise = 10160203806
  # password = your-password-here
  year = 2026-27

Run with:
  C:\Users\Admin\AppData\Local\hermes\hermes-agent\venv\Scripts\python
    esk_otr_api.py --config eshikshakosh.conf


WAY 4 — Python import (for embedding in other scripts)
-------------------------------------------------------
  from esk_otr_api import main_async
  import asyncio

  asyncio.run(main_async(
      udise="10160203806",
      password="your-password-here",
      academic_year="2026-27",
      output="my_report.xlsx"
  ))


================================================================================
  HOW TO RUN DIRECTLY FROM PYTHON (WITHOUT HERMES)
================================================================================

PREREQUISITES
-------------
1. Python 3.11+ installed and on PATH
2. Install required packages:

   pip install requests pandas openpyxl playwright

3. Install Playwright browser:

   python -m playwright install chromium

4. The script is at:
   C:\Users\Admin\Eshikshakosh_OTR_Report\esk_otr_api.py

RUN FROM COMMAND PROMPT
-----------------------
   cd C:\Users\Admin\Eshikshakosh_OTR_Report
   python esk_otr_api.py --udise 10160203806

   (it will prompt for password and captcha)

RUN FROM PYTHON SHELL / IDLE / JUPYTER
---------------------------------------
   import asyncio
   from esk_otr_api import main_async

   asyncio.run(main_async(
       udise="10160203806",
       password="your-password",
       academic_year="2026-27"
   ))

RUN FROM ANOTHER PYTHON SCRIPT
------------------------------
   import subprocess
   import os

   os.chdir(r"C:\Users\Admin\Eshikshakosh_OTR_Report")
   subprocess.run([
       "python", "esk_otr_api.py",
       "--udise", "10160203806",
       "--password", "your-password"
   ])


================================================================================
  WHAT THE SCRIPT DOES (STEP BY STEP)
================================================================================

Step 1: Login via Playwright (headless browser)
  - Opens Chrome headless (no visible window)
  - Goes to e-Shikshakosh login page
  - Clicks "School Login" radio button
  - Types UDISE (from --udise argument)
  - Types password (from --password or prompt)
  - Reads captcha text from page
  - TRIES TO AUTO-SOLVE: if captcha is a math problem like "8 * 2",
    calculates the answer automatically (16)
  - IF AUTO-SOLVE FAILS: prompts you to type the captcha answer manually
  - Clicks Submit
  - Captures JWT token + access token from login response
  - Closes browser

Step 2: Fetch Student List (API call)
  - Calls: POST https://eshikshakosh.bihar.gov.in:8443/student/viewStudentList
  - Gets all students in batches
  - Each student record has: name, code, father, aadhaar, mobile, class, etc.

Step 3: Fetch Student Details (parallel, 16 at a time)
  - Calls: POST .../student/studentInfo for each student
  - Gets: Mother Name, Bank Account No, IFSC Code, Account Holder Name,
    OTR Number, OTR Status, full unmasked Aadhaar

Step 4: Resolve Bank Names from IFSC
  - Looks up each IFSC code at ifsc.razorpay.com
  - Maps codes like BARB0SIWANX → "Bank of Baroda"
  - Caches results to avoid repeat lookups

Step 5: Build Excel File
  - Creates Student_OTR_Report_<UDISE>_<YEAR>.xlsx
  - 27 columns, all student rows + header
  - Formatted: colored header, borders, frozen top row, auto-filter
  - ID columns (Student Code, Aadhaar, Bank Account, IFSC, etc.)
    stored as TEXT to preserve leading zeros

Step 6: Print Summary
  - Shows total students, OTR registered/pending, Aadhaar count,
    bank account count, mother name count


================================================================================
  CAPTCHA HANDLING
================================================================================

AUTOMATIC (works for math captchas):
  Captcha: "Let's solve this math problem : 8 * 2"
  Script extracts "8 * 2", evaluates to 16, fills it in automatically.

MANUAL (when auto-solve fails):
  If the captcha format changes or evaluation fails, you will see:

    Captcha shown: Let's solve this math problem : 7 + 3
    Auto-captcha solve failed: ...
    Please solve the captcha manually in the browser window.
    Enter captcha answer: _

  Type the answer (e.g. "10") and press Enter.
  The script will fill it into the captcha field and continue.

TROUBLESHOOTING CAPTCHA:
  - If captcha says "Invalid captcha" after submit, the answer was wrong
  - The script will log the captcha text — check if the math is correct
  - Some captchas may not be math problems — manual entry is the fallback


================================================================================
  OUTPUT FILE CONTENTS
================================================================================

File: Student_OTR_Report_<UDISE>_<ACADEMIC_YEAR>.xlsx
      (e.g. Student_OTR_Report_10160203806_2026-27.xlsx)

Columns (27 total):
  1.  S.No.
  2.  Student Name
  3.  Student Code
  4.  Father's Name
  5.  Mother's Name
  6.  Class
  7.  Section
  8.  Roll No
  9.  OTR Number
  10. OTR Status
  11. Aadhaar Number
  12. Bank Account No
  13. IFSC Code
  14. Bank Name
  15. Account Holder Name
  16. Mobile Number
  17. DOB
  18. Gender
  19. Social Category
  20. Admission No
  21. Admission Date
  22. Stream
  23. CWSN
  24. Profile Updated
  25. School Name
  26. UDISE
  27. Academic Year

Sample data (first 5 rows):
  Row 1: AAKASH KUMAR | Code 202410161054823 | Father PRAHLAD KUMAR RAM
          Mother KAUSHALYA DEVI | Class 9 | Roll 12
          OTR: Pending | Aadhaar: 467019359802
          Bank: 30098100136196 | IFSC: BARB0SIWANX | Bank: Bank of Baroda

  Row 2: AARZOO PRAWEEN | Code 202410161047607 | Father MURTUZA KHAN
          Mother FAHAMIDA KHATUN | Class 12 | Roll 5
          OTR: Pending | Aadhaar: 995137318826
          Bank: 30098100133417 | IFSC: BARB0SIWANX

  Row 3: AATIF ALI | Code 202510161486705 | Father CHAND BABU SIDDIQUE
          Mother ANJUMARA | Class 12 | Roll 62
          OTR: Pending | Aadhaar: 665179450463
          Bank: 624602120000891 | IFSC: UBIN0562467 | Bank: Union Bank of India

  Row 4: ADIL ALI | Code 202510161431258 | Father SARFARAZ AHMAD
          Mother SAMSUN TABREZ | Class 12 | Roll 4
          OTR: Pending | Aadhaar: XXXX-XXXX-3149 (masked)
          Bank: 10010481408 | IFSC: IPOS0000001 | Bank: India Post Payments Bank

  Row 5: ADITYA KUMAR SAH | Code 202410160879770 | Father DEVENDRA SAH
          Mother LALI DEVI | Class 9 | Roll 10
          OTR: Pending | Aadhaar: 613850429963
          Bank: 1006601030161214 | IFSC: CBIN0R10001 | Bank: Uttar Bihar Gramin Bank

Summary from actual file:
  Total Students:    220
  OTR Registered:    0
  OTR Pending:       220
  Aadhaar present:   219 (1 student has masked/empty Aadhaar)
  Bank Accounts:     220 (all students have bank accounts)
  Mother Names:      220 (all students have mother names)


================================================================================
  HOW TO OPEN THE EXCEL FILE
================================================================================

Double-click in File Explorer:

  C:\Users\Admin\Eshikshakosh_OTR_Report\Student_OTR_Report_10160203806_2026-27.xlsx

Or open Excel → File → Open → browse to the folder above.

The file has:
  - Frozen top row (header stays visible when scrolling)
  - Auto-filter on all columns (click dropdown arrows to filter)
  - Colored header row
  - All ID numbers as TEXT (no scientific notation)


================================================================================
  TROUBLESHOOTING
================================================================================

PROBLEM: "python is not recognized"
SOLUTION: Use full path:
  C:\Users\Admin\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe
    esk_otr_api.py --udise 10160203806

PROBLEM: Password prompt not appearing
SOLUTION: Make sure you didn't pass --password on the command line.
  Without --password, the script prompts interactively.

PROBLEM: Login fails / captcha error
SOLUTION:
  - Check that UDISE (10160203806) and password are correct
  - If auto-captcha fails, type the answer manually when prompted
  - Check the output for "Captcha shown:" line to see what the captcha is

PROBLEM: "No students found"
SOLUTION: Check that UDISE is correct (10160203806) and academic
  year matches (2026-27). The school has 220 students in this year.

PROBLEM: SSL certificate warnings (yellow text in output)
SOLUTION: These are harmless warnings. The Bihar portal uses
  self-signed certificates. The script handles them. Add
  --verify-ssl to enable strict verification (may fail).

PROBLEM: Playwright not found / browser not installed
SOLUTION:
  pip install playwright
  python -m playwright install chromium

PROBLEM: Script runs but no Excel file created
SOLUTION: Check the output for errors. The script prints "Saved: <filename>"
  when successful. If it exits early, there will be an error message.


================================================================================
  SECURITY NOTE
================================================================================

DO NOT commit eshikshakosh.conf with your real password to GitHub.
The config file is a template — replace "your-password-here" with
your actual password only in your local copy.

The Excel file contains unmasked Aadhaar numbers for 219 students.
Keep it secure and share only with authorized personnel.


================================================================================
  QUICK REFERENCE CARD
================================================================================

RUN:   cd C:\Users\Admin\Eshikshakosh_OTR_Report
        python esk_otr_api.py --udise 10160203806
        (password prompted interactively)

 OUTPUT: Student_OTR_Report_10160203806_2026-27.xlsx

 STUDENTS:    220 (Class 9: 33, Class 10: 34, Class 11: 78, Class 12: 75)
 AADHAAR:     219 unmasked
 BANK:        220 accounts with IFSC codes
 MOTHER:      220 names
 OTR:         0 registered, 220 pending

 CAPTCHA:     Auto-solves math captchas; prompts manually if fails

================================================================================
