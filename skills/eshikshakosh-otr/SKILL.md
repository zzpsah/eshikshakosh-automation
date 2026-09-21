---
name: eshikshakosh-otr
description: Generate e-Shikshakosh Bihar student OTR report Excel from local machine.
version: 1.0.0
author: zzpsah, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [eshikshakosh, bihar, student-report, excel, otr]
    related_skills: []
---

# Eshikshakosh OTR Report Generator

Generate a complete student OTR (One Time Registration) verification report Excel for e-Shikshakosh Bihar portal schools. Logs in via Playwright, fetches all students with Mother Name, Bank Account, IFSC, Bank Name, OTR Number, OTR Status, and unmasked Aadhaar.

## When to Use

- User needs a student OTR report Excel for a Bihar e-Shikshakosh school
- User has UDISE code and portal password
- User is on a machine with Python 3.11+ and Playwright installed
- Report needed for TETAHALI school (UDISE 10160203806) or any other Bihar school

## Prerequisites

**On the machine running the script:**

```bash
pip install requests pandas openpyxl playwright
python -m playwright install chromium
```

**Files in this skill directory:**
- `esk_otr_api.py` — the main script
- `esk_oshakosh.conf` — config template
- `READ_ME_FIRST.txt` — full documentation

## How to Run

### Command line (interactive password prompt)

```bash
cd skills/eshikshakosh-otr
python esk_otr_api.py --udise 10160203806
# Password: [prompted interactively]
```

### Command line with password flag

```bash
python esk_otr_api.py --udise 10160203806 --password "your-password"
```

### Config file

Edit `esk_otr_api.conf` (uncomment and set password), then:

```bash
python esk_otr_api.py --config eshikshakosh.conf
```

### As a Python module

```python
import asyncio
from esk_otr_api import main_async

asyncio.run(main_async(
    udise="10160203806",
    password="your-password",
    academic_year="2026-27",
    output="my_report.xlsx"
))
```

## Captcha Handling

The script auto-solves math captchas (e.g. "8 * 2" → 16). If auto-solve fails:
- The script logs the captcha text
- Prompts the user to type the answer manually
- Fills it in and continues

## Output

Excel file: `Student_OTR_Report_<UDISE>_<YEAR>.xlsx`

27 columns including: Student Name, Code, Father, Mother, Class, Roll No, OTR Number, OTR Status, Aadhaar (unmasked), Bank Account No, IFSC, Bank Name, Account Holder, Mobile, DOB, Gender, Social Category, etc.

220 students for TETAHALI school (UDISE 10160203806).

## Arguments

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--udise`, `-u` | Yes | — | Portal User ID / School UDISE |
| `--password`, `-p` | No | — | Portal password (prompts if omitted) |
| `--year`, `-y` | No | 2026-27 | Academic year |
| `--output`, `-o` | No | auto-generated | Output Excel filename |
| `--config`, `-c` | No | — | Path to config file |
| `--verify-ssl` | No | off | Enable SSL verification |

## Security Notes

- Do NOT commit `esk_otr_api.conf` with real password to the repo
- The Excel contains unmasked Aadhaar numbers — keep secure
- Password is prompted interactively by default (not visible in command line)

## Files

```
skills/eshikshakosh-otr/
├── SKILL.md                      # This file
├── esk_otr_api.py                # Main script (19 KB)
├── eshikshakosh.conf             # Config template
├── READ_ME_FIRST.txt             # Full documentation (12 KB)
└── Student_OTR_Report_2026-27.xlsx  # Sample output (43 KB)
```
