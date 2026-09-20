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
  FILES ON YOUR COMPUTER
================================================================================

Location: C:\Users\Admin\

  FILE                              SIZE      WHAT IT IS
  --------------------------------  --------  ---------------------------
  esk_otr_api.py                    18,342    THE SCRIPT (run this)
  eshikshakosh.conf                 73        Config (UDISE + password)
  Student_OTR_Report_10160203806_   43,803    THE OUTPUT Excel file
    2026-27.xlsx                              (generated after run)


================================================================================
  HOW TO RUN — 3 WAYS
================================================================================

WAY 1 — Direct command (simplest)
-----------------------------------
Open Command Prompt and run:

  cd C:\Users\Admin

  C:\Users\Admin\AppData\Local\hermes\hermes-agent\venv\Scripts\python
    esk_otr_api.py --udise 10160203806 --password "Purpl3Tr@1n"


WAY 2 — Using config file (password not visible in command)
------------------------------------------------------------
The config file already exists at:

  C:\Users\Admin\eshikshakosh.conf

Content:
  [eshikshakosh]
  udise = 10160203806
  password = Purpl3Tr@1n
  year = 2026-27

Run with:
  C:\Users\Admin\AppData\Local\hermes\hermes-agent\venv\Scripts\python
    esk_otr_api.py --config C:\Users\Admin\eshikshakosh.conf


WAY 3 — Interactive password prompt
------------------------------------
  C:\Users\Admin\AppData\Local\hermes\hermes-agent\venv\Scripts\python
    esk_otr_api.py --udise 10160203806

  It will ask: Password:  (type Purpl3Tr@1n, invisible)


================================================================================
  PYTHON & SCRIPT PATH (for reference)
================================================================================

Python executable:
  C:\Users\Admin\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe

Script:
  C:\Users\Admin\esk_otr_api.py

Config:
  C:\Users\Admin\eshikshakosh.conf

Output (after run):
  C:\Users\Admin\Student_OTR_Report_10160203806_2026-27.xlsx


================================================================================
  WHAT THE SCRIPT DOES (STEP BY STEP)
================================================================================

Step 1: Login via Playwright (headless browser)
  - Opens Chrome headless
  - Goes to e-Shikshakosh login page
  - Clicks "School Login" radio button
  - Types UDISE: 10160203806
  - Types password: Purpl3Tr@1n
  - Reads captcha, solves math problem (e.g. "8 * 2" → 16)
  - Clicks Submit
  - Captures JWT token + access token from login response
  - Closes browser

Step 2: Fetch Student List (API call)
  - Calls: POST https://eshikshakosh.bihar.gov.in:8443/student/viewStudentList
  - Gets all 220 students in batches of 100
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
  - Creates Student_OTR_Report_10160203806_2026-27.xlsx
  - 27 columns, 220 student rows + header
  - Formatted: colored header, borders, frozen top row, auto-filter
  - ID columns (Student Code, Aadhaar, Bank Account, IFSC, etc.)
    stored as TEXT to preserve leading zeros

Step 6: Print Summary
  - Shows total students, OTR registered/pending, Aadhaar count,
    bank account count, mother name count


================================================================================
  OUTPUT FILE CONTENTS
================================================================================

File: C:\Users\Admin\Student_OTR_Report_10160203806_2026-27.xlsx

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

Double-click this file in File Explorer:

  C:\Users\Admin\Student_OTR_Report_10160203806_2026-27.xlsx

Or open Excel → File → Open → browse to:
  C:\Users\Admin\
  and select: Student_OTR_Report_10160203806_2026-27.xlsx

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
    esk_otr_api.py --udise 10160203806 --password "Purpl3Tr@1n"

PROBLEM: Login fails / captcha error
SOLUTION: The script solves simple math captchas automatically.
  If captcha format changes, the script may fail. Check the output
  for "Captcha answer" line — if it shows wrong answer, the portal
  may have changed captcha format.

PROBLEM: "No students found"
SOLUTION: Check that UDISE is correct (10160203806) and academic
  year matches (2026-27). The school has 220 students in this year.

PROBLEM: SSL certificate warnings (yellow text in output)
SOLUTION: These are harmless warnings. The Bihar portal uses
  self-signed certificates. The script handles them. Add
  --verify-ssl to enable strict verification (may fail).

PROBLEM: Playwright not found
SOLUTION: The script requires Playwright. It was installed at:
  C:\Users\Admin\AppData\Local\hermes\hermes-agent\venv\Lib\site-packages\playwright
  Browser binaries at:
  C:\Users\Admin\AppData\Local\ms-playwright\chromium-1243


================================================================================
  SECURITY NOTE
================================================================================

The config file C:\Users\Admin\eshikshakosh.conf contains your password
in plain text. Delete it after use:

  del C:\Users\Admin\eshikshakosh.conf

The Excel file contains unmasked Aadhaar numbers for 219 students.
Keep it secure and share only with authorized personnel.


================================================================================
  QUICK REFERENCE CARD
================================================================================

RUN:   cd C:\Users\Admin
        C:\Users\Admin\AppData\Local\hermes\hermes-agent\venv\Scripts\python
          esk_otr_api.py -u 10160203806 -p "Purpl3Tr@1n"

OUTPUT: C:\Users\Admin\Student_OTR_Report_10160203806_2026-27.xlsx

STUDENTS: 220 (Class 9: 33, Class 10: 34, Class 11: 78, Class 12: 75)
AADHAAR:  219 unmasked
BANK:     220 accounts with IFSC codes
MOTHER:   220 names
OTR:      0 registered, 220 pending

================================================================================
