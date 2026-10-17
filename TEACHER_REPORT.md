# Teacher Report — e-ShikshaKosh

Read-only export of teacher details from e-ShikshaKosh to an Excel workbook. One script
serves every school; nothing school-specific is hardcoded in the extractor.

Two exports are available:

| Runner | Output | Use |
|---|---|---|
| `run_teacher_report.sh` | list of teachers, 110 fields each | quick roster / Excel |
| `run_teacher_detail_report.sh` | list **plus** per-teacher detail sections | full profile |

## Script inventory and maintenance notes

See [local-script/TEACHER_SCRIPTS.md](local-script/TEACHER_SCRIPTS.md) for the current script inventory, canonical entry points, legacy/diagnostic scripts, safe usage, and review findings.

## Vercel workflow portal

Portal: [https://eshikshakosh.vercel.app](https://eshikshakosh.vercel.app). The frontend is currently a command guide for the existing Oracle VPS workflows; it does not yet generate or deliver reports directly. See [web/README.md](web/README.md) for the current integration boundary and safe next steps.

## List export

```bash
cd ~/projects/eshikshakosh-automation

local-script/run_teacher_report.sh --school Sahaspur
local-script/run_teacher_report.sh --school 10130106304
local-script/run_teacher_report.sh --list                 # list known schools
```

## Detail export (registration + education + service history)

```bash
cd ~/projects/eshikshakosh-automation

local-script/run_teacher_detail_report.sh --school Sahaspur
ESHIKSHAKOSH_DETAIL_LIMIT=2 local-script/run_teacher_detail_report.sh --school Sahaspur   # smoke test
```

Output: `~/exports/Teacher_Details_<School Name>_<timestamp>.xlsx` with sheets:

| Sheet | Contents |
|---|---|
| `Teachers` | roster: id, name, title, appointment, mobile, school, joining dates, subject |
| `Registration Info` | one row per teacher — personal, contact, address, IDs, posting |
| `Education` | one row per qualification (pre-service and in-service) |
| `Professional` | one row per professional/vocational qualification |
| `Other Info` | one row per teacher, other information |
| `Training` | one row per training record |
| `Service History` | one row per posting — district, block, school, designation, subject, from/to |

Sections that genuinely have no records for a school show `No records for this school`
rather than being omitted.

### Detail endpoints (all read-only POSTs, keyed by the teacher's encrypted `encId`)

| Endpoint | Section |
|---|---|
| `/teacher/registrationInfo` | registration, personal, address |
| `/teacher/getTeacherDetails` | basic summary |
| `/teacher/viewTeacherEducationInfo` | qualifications |
| `/teacher/viewTeacherProfessionalInfo` | professional qualifications |
| `/teacher/viewTeacherOtherInfo` | other information |
| `/teacher/viewTeacherTrainingInfo` | training and language |
| `/teacher/getExistingServiceInfo` | posting history |

The `encId` comes from the list response for that teacher. Every call is issued through
the live browser session so the portal's own auth headers apply — a plain `requests`
session gets HTTP 401.

## Credential paths (both runners)

| Path | When | Stored? |
|---|---|---|
| `--school <name>` | registered school | yes, Bitwarden |
| `--udise … --username … --password …` | one-time, unregistered school | no |
| `--udise … --user-key … --pass-key …` | registered Bitwarden keys, unregistered school | yes, Bitwarden |

`--username` and `--password` must be given together; `--udise` is required on every path.
One-time credentials are used for that run only — never written to disk, memory, Git, or
logs, and never printed.

## Required environment (set by the runners)

| Variable | Meaning |
|---|---|
| `ESHIKSHAKOSH_USERNAME` | portal login id (11-digit UDISE or teacher id) |
| `ESHIKSHAKOSH_PASSWORD` | portal password |
| `ESHIKSHAKOSH_TARGET_UDISE` | UDISE of the school to export — mandatory |
| `ESHIKSHAKOSH_OUT` | output directory (optional, default `~/exports`) |
| `ESHIKSHAKOSH_DETAIL_LIMIT` | detail runner only: cap teachers, for a smoke test |

The extractor refuses to start if any of the first three is missing. There is no default
school and no default UDISE.

## School registry — `local-script/esk_schools.py`

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

`find()` resolves a school by exact UDISE, registry key, or any alias (case-insensitive).
An unrecognized school exits with code 3 and prints the `--list` hint.

## Why the target school must be explicit

The legacy `local-script/esk_teacher_browser_extract.py` hardcodes
`EXPECTED_UDISE = '10160203806'` and `EXPECTED_SCHOOL_ID = 42645` (UMV Tetahali) and
injects `searchSchoolId` into the request. Running it under a different school's login
still returned Tetahali's teachers while its own scope check passed — a silent
wrong-school export.

Rules the current extractors follow:

- The numeric `searchSchoolId`, district/block/cluster, and encrypted `schoolId`/`userId`
  always come from the live portal request of the logged-in user.
- Only `offset`, `limit`, and `schoolUdiseCode` are overridden, and `schoolUdiseCode` must
  be supplied explicitly.
- Every returned row is validated against the target UDISE. Any mismatch aborts the export
  before a workbook is written.
- Never reintroduce a hardcoded numeric school ID or a default school.

## Browser-based extraction flow

1. Retrieve credentials through the protected Bitwarden wrapper.
2. Playwright logs into the portal and solves the displayed arithmetic captcha.
3. Playwright opens the teacher search page and clicks Search.
4. The script captures the real browser `/teacher/viewTeacher` request and response. It
   keeps the browser's authentication headers and session; it does not switch to a
   separate `requests.Session`.
5. The live read-only list request is expanded to a 100-record page and re-scoped to the
   target UDISE only. Further pages are fetched through browser `fetch` with the same
   captured browser auth headers, until `totalRecord` is reached.
6. The detail runner then calls each section endpoint per teacher with that teacher's
   `encId`, and refuses to write a workbook if pagination is incomplete, the UDISE scope
   fails, or teacher IDs repeat.

## Security and scope

- Read-only: login, search, fetch, and local Excel export only. No teacher record is
  created, edited, approved, or submitted.
- Passwords, bearer tokens, encrypted IDs, and teacher PII are not printed to console.
- Generated workbooks are stored outside Git under `~/exports` and restricted to mode `0600`.
- `local-script/esk_teacher_browser_extract_school.py` (list) and
  `local-script/esk_teacher_detail_extract.py` (detail) are the canonical runner targets.
- The legacy `esk_teacher_extract.py` / `esk_teacher_browser_extract.py` implementations are
  kept for reference only: their separate HTTP session received HTTP 401, and the old
  browser copy hardcoded the Tetahali school ID.

## Adding a school — checklist

1. Store the credentials in Bitwarden Secrets Manager with the school's structured keys.
2. Confirm the school's 11-digit UDISE from the portal.
3. Add one `SCHOOLS` entry in `local-script/esk_schools.py`.
4. Run `local-script/run_teacher_detail_report.sh --school "<alias>"` and check the printed
   school name matches the requested school before sending the file.

