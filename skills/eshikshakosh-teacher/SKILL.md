---
name: eshikshakosh-teacher
description: "Extract teacher details from e-ShikshaKosh to Excel (list and full detail)."
version: 1.0.0
author: zzpsah
license: MIT
platforms: [linux]
metadata:
  tags: [eshikshakosh, bihar, teacher-report, teacher-data, excel, service-history]
  related_skills: [eshikshakosh-otr]
---

# e-ShikshaKosh Teacher Report

Use this skill when an authorized user asks for teacher data, teacher details, a teacher
list, or a teacher Excel export from the e-ShikshaKosh portal.

**This is separate from `eshikshakosh-otr` which is for STUDENT/OTR reports only.**

## Trigger examples

- `teacher details excel`
- `teacher list bhejo`
- `sabhi teachers ka data chahiye`
- `teacher report`
- `eshikshakosh teacher export`
- `teachers ki education details`
- `service history of teachers`
- `Teachers_*.xlsx`

## Two exports

| Runner | Output | Use |
|---|---|---|
| `local-script/run_teacher_report.sh` | teacher list, 110 fields each | quick roster |
| `local-script/run_teacher_detail_report.sh` | list **plus** per-teacher detail sections | full profile |

Use the detail runner when the user asks for "full detail", education/qualification,
professional info, training, or service history (posting history).

```bash
cd ~/projects/eshikshakosh-automation

# List export
local-script/run_teacher_report.sh --school Sahaspur
local-script/run_teacher_report.sh --school 10130106304
local-script/run_teacher_report.sh --list

# Detail export (registration + education + service history)
local-script/run_teacher_detail_report.sh --school Sahaspur
ESHIKSHAKOSH_DETAIL_LIMIT=2 local-script/run_teacher_detail_report.sh --school Sahaspur   # smoke test

# Unregistered school — one-time credentials, nothing saved
local-script/run_teacher_detail_report.sh --udise <UDISE> --username <login> --password <password>
```

## Outputs

List: `~/exports/Teachers_<School Name>_browser_<timestamp>.xlsx` — 110+ fields per
teacher, priority fields first, auto-sized columns.

Detail: `~/exports/Teacher_Details_<School Name>_<timestamp>.xlsx` with sheets:

| Sheet | Contents |
|---|---|
| `Teachers` | roster: id, name, title, appointment, mobile, school, joining dates, subject |
| `Registration Info` | one row per teacher — personal, contact, address, IDs, posting |
| `Education` | one row per qualification (pre-service and in-service) |
| `Professional` | one row per professional/vocational qualification |
| `Other Info` | one row per teacher, other information |
| `Training` | one row per training record |
| `Service History` | one row per posting — district, block, school, designation, subject, from/to |

A section with genuinely no records for a school says `No records for this school` rather
than being silently omitted.

## Detail endpoints

All read-only POSTs, keyed by the teacher's encrypted `encId` from the list response:

| Endpoint | Section |
|---|---|
| `/teacher/registrationInfo` | registration, personal, address |
| `/teacher/getTeacherDetails` | basic summary |
| `/teacher/viewTeacherEducationInfo` | qualifications |
| `/teacher/viewTeacherProfessionalInfo` | professional qualifications |
| `/teacher/viewTeacherOtherInfo` | other information |
| `/teacher/viewTeacherTrainingInfo` | training and language |
| `/teacher/getExistingServiceInfo` | posting history |

Issue every detail call through the live browser session so the portal's own auth headers
apply. A plain `requests` session gets HTTP 401, and a browser `fetch` without the captured
`authorization` / `accesstoken` headers also gets HTTP 401. The `encId` is per teacher and
is never guessed or reused across teachers.

## Works for any school — registry driven

The extractors hardcode no school. They read `ESHIKSHAKOSH_TARGET_UDISE` and refuse to
start without it. The runner resolves the school through `local-script/esk_schools.py` and
picks that school's own Bitwarden keys.

```python
SCHOOLS = {
    "UMV_SAHASPUR": {
        "udise": "10130106304",
        "username_key": "ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_USERNAME",
        "password_key": "ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_PASSWORD",
        "aliases": ["sahaspur", "umv sahaspur", ...],
    },
    ...
}
```

Adding a school needs no code change: store its Bitwarden secrets, then add one entry with
`udise`, `username_key`, `password_key` and `aliases`. An unrecognized school exits 3 and
prints the `--list` hint.

## Credential paths

| Path | When | Stored? |
|---|---|---|
| `--school <name>` | registered school | yes, Bitwarden |
| `--udise … --username … --password …` | one-time, unregistered school | no |
| `--udise … --user-key … --pass-key …` | registered Bitwarden keys, unregistered school | yes, Bitwarden |

`--username` and `--password` must be given together; `--udise` is required on every path.
One-time credentials are used for that run only — never written to disk, memory, Git, or
logs, and never printed.

## Required environment

| Variable | Meaning |
|---|---|
| `ESHIKSHAKOSH_USERNAME` | portal login id (11-digit UDISE or teacher id) |
| `ESHIKSHAKOSH_PASSWORD` | portal password |
| `ESHIKSHAKOSH_TARGET_UDISE` | UDISE of the school to export — mandatory, no default |
| `ESHIKSHAKOSH_OUT` | output directory (optional, default `~/exports`) |
| `ESHIKSHAKOSH_DETAIL_LIMIT` | detail runner only: cap teachers, for a smoke test |

## CRITICAL PITFALL — hardcoded school ID silently exports the wrong school

The legacy `local-script/esk_teacher_browser_extract.py` hardcodes
`EXPECTED_UDISE = '10160203806'` and `EXPECTED_SCHOOL_ID = 42645` (UMV Tetahali) and
injects `searchSchoolId` into the request payload. Running it under a *different* school's
login still returns the hardcoded school's teachers, and its own UDISE scope check then
passes — a silent wrong-school export.

Rule: the numeric `searchSchoolId`, district/block/cluster, and encrypted
`schoolId`/`userId` must come from the live portal request of the logged-in user. Only
`offset`, `limit`, and `schoolUdiseCode` may be overridden, and the target UDISE must be
supplied explicitly. Never reintroduce a hardcoded numeric school ID or a default school.

## Browser request flow

1. Playwright logs in (arithmetic captcha solved from the portal's own text).
2. The teacher search page's `/teacher/viewTeacher` POST is intercepted; the captured
   payload keeps the portal's own district/block/cluster and encrypted `schoolId`/`userId`,
   and only `offset`, `limit`, `schoolUdiseCode` are overridden.
3. The response is read from the browser session; further pages use browser `fetch` with the
   same captured auth headers.
4. The detail runner then calls each section endpoint per teacher with that teacher's
   `encId`.
5. The export refuses to write a workbook if pagination is incomplete, the UDISE scope
   fails, or teacher IDs repeat.

Do not build a separate `requests.Session()` — port 8443 requires the JWT headers and a
plain session returns HTTP 401.

## Authorization guard

The generated workbook can contain unmasked teacher data including Aadhaar, PAN, mobile,
and bank details.

- Send only to an authorized requester in a private chat
- Do not send to groups
- Do not upload to GitHub

## Failure behavior

- Login failure → report exact error
- Captcha failure → report "captcha auto-solve failed"
- API 401 → token capture failed, check credentials
- API 400 → payload structure may have changed
- API 500 → retry with backoff

## File structure

```
~/projects/eshikshakosh-automation/
├── local-script/
│   ├── run_teacher_report.sh                  # list export entry point
│   ├── run_teacher_detail_report.sh           # detail export entry point
│   ├── esk_schools.py                        # school -> credentials/UDISE registry
│   ├── esk_teacher_browser_extract_school.py  # canonical list extractor (any school)
│   ├── esk_teacher_detail_extract.py          # canonical detail extractor (any school)
│   ├── esk_teacher_extract.py                 # field/header mapping + legacy API impl
│   └── esk_otr_api.py                         # student API (reference)
├── skills/
│   ├── eshikshakosh-otr/SKILL.md              # student/OTR report
│   └── eshikshakosh-teacher/SKILL.md          # this file
├── .venv/
└── requirements.txt
```

## Dependencies

```bash
cd ~/projects/eshikshakosh-automation
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
```
