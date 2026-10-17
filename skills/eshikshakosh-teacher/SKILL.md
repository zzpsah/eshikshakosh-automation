---
name: eshikshakosh-teacher
description: Extract teacher data from e-ShikshaKosh portal.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [eshikshakosh, bihar, teacher-report, excel, teacher-data]
    related_skills: [eshikshakosh-report]
---

# e-ShikshaKosh Teacher Data Extraction

## When to Use

Use this skill when an authorized user asks for:
- Teacher details, teacher list, or teacher registration data
- Teacher Excel export from e-ShikshaKosh portal
- Any teacher-related data extraction (all 110+ fields)

Do NOT use for student/OTR reports — use `eshikshakosh-report` skill instead.

## Key differences from student API

Teacher API is **fundamentally different** from the student OTR API. Do not assume student patterns work:

| Aspect | Student API | Teacher API |
|---|---|---|
| List endpoint | `/student/viewStudentList` | `/teacher/viewTeacher` |
| Detail endpoint | `/student/studentInfo` (separate call) | **Not needed** — list returns all 110+ fields |
| Auth headers | `authorization` + `accesstoken` | `authorization` + `accesstoken` + `authtoken` + `authaccess` (all 4 required) |
| School ID | Numeric `searchSchoolId` | Encrypted `schoolId` (Laravel token) + numeric `searchSchoolId` |
| User ID | Not in payload | Encrypted `userId` (Laravel token) |
| Payload complexity | 4 fields | 30+ fields |
| Fields per student | ~27 | ~110 |

## Core procedure

### Step 1: Login and capture tokens + encrypted IDs

Login via Playwright to capture JWT + access_token, then navigate to teacher page to intercept the `teacherCount` API call which contains encrypted `schoolId` and `userId`.

```bash
cd ~/projects/eshikshakosh-automation
~/.local/bin/eshikshakosh-run .venv/bin/python modules/teacher/scripts/esk_teacher_extract.py
```

The script:
1. Logs in via Playwright (captcha auto-solved)
2. Captures JWT + access_token from `/auth/login` response
3. Navigates to teacher registration page
4. Intercepts `/teacher/teacherCount` response to extract encrypted `schoolId` and `userId`
5. Uses `requests.Session()` with full 4-header auth to call `/teacher/viewTeacher`
6. Exports all 110+ fields to Excel

### Step 2: Auth headers (ALL 4 required)

```python
headers = {
    "authorization": f"Bearer {jwt_token}",
    "accesstoken": f"Bearer {access_token}",
    "authtoken": f"Bearer {jwt_token}",
    "authaccess": f"Bearer {access_token}",
    "content-type": "application/json",
    "origin": "https://eshikshakosh.bihar.gov.in",
    "referer": "https://eshikshakosh.bihar.gov.in/",
}
```

**Pitfall**: Missing any one of the 4 auth headers causes 401 Unauthorized. The JWT goes in `authorization` + `authtoken`; the access_token goes in `accesstoken` + `authaccess`.

### Step 3: Encrypted IDs (critical)

The `schoolId` and `userId` in the teacher payload are **encrypted Laravel tokens** (e.g. `eyJpdi...`), NOT numeric IDs. They must be intercepted from the browser's `/teacher/teacherCount` API call.

**Pitfall**: Using numeric school ID instead of encrypted token causes 400 Bad Request with "Something went wrong."

### Step 4: Full payload structure

The `/teacher/viewTeacher` endpoint requires 30+ fields. Minimal working payload:

```json
{
  "offset": "0",
  "limit": "100",
  "serviceType": "Search",
  "searchDistrictId": 16,
  "searchBlockId": 219,
  "searchClusterId": 2471,
  "searchSchoolId": 42645,
  "searchTeacherTitle": "",
  "searchNatureOfAppointmt": "",
  "searchTeacherId": "",
  "schoolUdiseCode": "",
  "searchTeacherTempLoginId": "",
  "searchTeacherName": "",
  "searchStatusWise": "",
  "searchVerification": "",
  "schoolId": "<encrypted>",
  "userId": "<encrypted>",
  "loginUserTypeId": 2,
  "district": 16,
  "block": 219,
  "cluster": 2471,
  "searchDeputationWise": "1",
  "searchTeacherSubTitle": "",
  "searchSchoolManagement": "",
  "searchSchoolCategory": "",
  "scDistrictName": "",
  "scBlockName": "",
  "scClusterName": "",
  "scSchoolName": "",
  "scAppointmtName": "",
  "scTeacherTypeName": "",
  "scManagementName": "",
  "scStatusName": "",
  "scDeputName": "",
  "scTeacherSubTypeName": ""
}
```

**Pitfall**: Omitting any required field causes 400. Intercept the actual browser request to get the exact field list — it varies by school type.

### Step 5: Use requests.Session() not page.evaluate(fetch())

After Playwright login, close the browser and use Python `requests.Session()` for API calls. Browser session cookies do NOT work with the 8443 API — it requires the 4 auth headers.

**Pitfall**: `page.evaluate(fetch(...))` returns 401 even when logged in. The 8443 API does not accept browser session cookies; it only accepts the 4 auth headers.

## Excel export

The extraction script exports a **curated 28-column format** (not all 110+ raw fields). The column order is fixed per user preference:

1. Serial No (`slNo`)
2. Temp Login ID (`teacherLoginCode`)
3. Teacher Name (`teacherName`)
4. Gender (`gender` — readable label from `registrationInfo`; `1`→`Male` / `2`→`Female` only as fallback)
5. Marital Status (`maritalStatus` — readable label, e.g. `Single` / `Married`)
6. Date of Birth (`DOB`)
7. Teacher Title (`teacherTitle`)
8. Nature of Appointment (`natureOfAppointmt`)
9. Service Joining Date (`serviceJoiningDt`)
10. Joining Current School Date (`joiningCurrentSchoolDt`)
11. Class Category (`classCategory`)
12. Appointed Subject (`appointedSubject`)
13. Mobile (`mobile`)
14. Email (`teacherEmail`)
15. PAN Number (`panNo`)
16. Employee Code / HRMS ID (`employeeCode`)
17. PRAN Number (`pranNo`)
18. GPF Number (`gpfNo`)
19. UAN Number (`uanNo`)
20. Aadhaar Number (`aadhaarNo`)
21. Social Category (`socialCategory`)
22. Permanent Domicile Number (`pDomicileNumber`)
23. Mother Name (`motherName`)
24. Father Name (`fatherName`)
25. Current Address (combined cell)
26. Permanent Address (combined cell)
27. School Name (`schoolName`)
28. School UDISE Code (`schoolUdiseCode`)

### Address combination

Addresses are combined into single cells with labeled fields (comma-separated):
`House: xxx, Street: xxx, Village: xxx, PIN: xxx, State: xxx, District: xxx, Block: xxx, Post Office: xxx`

Empty fields are omitted. The `_permanentAddress` and `_currentAddress` are computed fields (prefixed with `_`) — they must be included in the export even though they don't exist in the raw API data.

**Pitfall**: Do NOT use multi-line address format (newlines). User rejected it — cells become too tall and unreadable. Comma-separated single-line is the preferred format.

### Gender conversion

Gender codes are converted: `1` → `Male`, `2` → `Female`. Unmapped codes remain unchanged.

### Professional Excel formatting

Match the student OTR report style:
- Light blue header row (`F2F4F7`) with dark blue bold text (`1F2937`), size 10, centered, wrap enabled
- Thin gray borders (`D1D5DB`) on all cells (header + data)
- Data cells: regular text (`111827`), size 10, centered
- AutoFilter on the header row
- Frozen top row (`freeze_panes = "A2"`)
- Auto-fit column widths based on content (header + data), capped at 50 characters

### PITFALL — remaining keys must not be appended

When building the export column list, only include fields from the `priority_fields` list that exist in the raw data. Do NOT append `remaining_keys` (all other raw fields not in the priority list) — this was a bug that caused 110+ columns to export instead of the curated 28. The fix: `all_columns = priority_keys` only.

Computed fields (prefixed with `_`) must be explicitly included even though they don't exist in the raw API data: `priority_keys = [k for k in priority_fields if k in all_keys or k.startswith('_')]`.

### Ignored fields

The following raw fields are **not** exported: `prefix`, `firstName`, `middleName`, `lastName`, `teacherCode`, `teacherType`, `religion`, `disabilityStatus`, `clusterName`, `districtCode`, `blockCode`, `clusterCode`, `appointingAuth`, `appointmentType`, `jfDistrictCode`, `pDomicile` (text), `isTeacherUpdatePermanentAddress`, `isPAddressCorrect`, `status`, `lastServiceStatus`, `profileStatus`, `verificationStatus`, `verificationRemarks`, `verificationDate`, `salaryInfoStatus`, `serviceInfoStatus`, `pendingAt`, `changeRequestStatus`, `changeRequestStatusRemarks`, `verifiedDataStatus`, `editProfileStatus`, `scModificationReqStatus`, `schRevertsts`, `createdOn`, `createdBy`, `isPrivateTeacher`, `updateDeputationStatus`, `beoVerifiedOn`, `niyojitTchCretedUpdatedDPO`, `niyojitTchCretedUpdatedDpoOn`, `ccVerifiedSts`, `ccVerifiedOn`, `encId`, `schoolId`, `scDistrictId`, `scBlockId`, `pranGpfUanEditStatus`, `profileColor`, `salaryInfoColor`, `serviceInfoColor`, `educationInfoStatus`, `educationInfoColor`, `subjectCategoryUpdateStatus`, `resetAddressUpdate`, `awardStatus`, `scClusterId`, `districtId`.

## Full detail extraction (7 sheets)

The current implementation does NOT scrape the detail page's tabs. It issues the portal's own
JSON endpoints from inside the authenticated browser session — one call per teacher per
section. Tab-text scraping was the earlier approach, and it is what left sheets blank; do not
reintroduce it.

Procedure (`modules/teacher/scripts/esk_teacher_detail_extract.py`):

1. Log in, click Search, capture the live `/teacher/viewTeacher` request — keep its auth
   headers and paginate with them until `totalRecord` is reached.
2. Validate every returned row against `ESHIKSHAKOSH_TARGET_UDISE` and abort before writing a
   workbook on any mismatch.
3. For each teacher, POST the section endpoints keyed by that teacher's `encId` (see the
   endpoint table below) through `page.evaluate(fetch(...))`.
4. Tag and merge the two education lists, then write the 7-sheet workbook.
5. Record a section that errors and keep going — one bad section must not abort the export.

**Pitfall — new tab capture** (only if you fall back to tab scraping): `context.expect_page()` does NOT reliably capture new tabs opened by link clicks. Use page-count diffing instead:
```python
pages_before = len(context.pages)
await link.click()
await page.wait_for_timeout(3000)
if len(context.pages) > pages_before:
    new_page = context.pages[-1]
    text = await new_page.evaluate('() => document.body.innerText')
    await new_page.close()
```

## Multi-school support

Wrapper `eshikshakosh-run` is **hardcoded to Tetahali** credentials. For any other school, set env vars manually and bypass the wrapper:

```bash
export ESHIKSHAKOSH_USERNAME=$(bws-hermes secret get ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_USERNAME 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['value'])")
export ESHIKSHAKOSH_PASSWORD=$(bws-hermes secret get ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_PASSWORD 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['value'])")
~/projects/eshikshakosh-automation/.venv/bin/python ~/projects/eshikshakosh-automation/modules/teacher/scripts/esk_teacher_extract.py
```

### Three-raasta approach

| Raasta | Kab | Save hota hai? |
|---|---|---|
| `--school <naam>` | registered school (Bitwarden) | haan, Bitwarden |
| `--udise … --username … --password …` | one-time, koi bhi school | nahi |
| `--udise … --user-key … --pass-key …` | Bitwarden keys, unregistered school | haan, Bitwarden |

Default to `--school` for known schools. Use `--udise` + `--username` + `--password` for one-time extractions without saving creds to Bitwarden.

## Known school registry

| School | Username key | Password key | Numeric schoolId |
|---|---|---|---|
| UMV Tetahali | `ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_USERNAME` | `ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_PASSWORD` | 42645 |
| UMV Sahaspur | `ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_USERNAME` | `ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_PASSWORD` | (intercept from browser) |

## Password security pitfall

**`--password` on command line persists in shell history.** Always use env vars for sensitive credentials:

```bash
# GOOD — env var, not in history
ESHIKSHAKOSH_USERNAME=<login> ESHIKSHAKOSH_PASSWORD=*** \
  modules/teacher/run_teacher_report.sh --udise 10130106304

# BAD — visible in shell history
modules/teacher/run_teacher_report.sh --udise 10130106304 --username <login> --password <password>
```

## Repository module layout

The repo is split by functional module. Teacher work lives only under `modules/teacher/`.

```
modules/student/   student OTR: run_report.sh, scripts/, notebooks/
modules/teacher/   teacher: run_teacher_report.sh, run_teacher_detail_report.sh, scripts/, archive/
shared/            cross-module: esk_schools.py (school/credential registry), wrapper config
```

Runners resolve the repo root as `$(dirname "$0")/../..`. A new workflow becomes
`modules/<name>/` with its own README, scripts and runner — never another flat root-level
script collection. `docs/VPS-PATHS.md` owns the physical path map.

## Two scripts — keep them SEPARATE

User directive: the browser-based and API-based methods stay separate. Do NOT merge them into
one script. An earlier merged `esk_teacher_unified.py` was deleted at the user's direction —
do not recreate it, and do not add a third export path.

| Script | Method | Output |
|---|---|---|
| `modules/teacher/scripts/esk_teacher_list.py` | API (list + per-teacher `registrationInfo`) | 28-col list with combined address |
| `modules/teacher/scripts/esk_teacher_detail_extract.py` | Browser / Playwright | 7-sheet full detail |

"Keep them separate" governs structure, not correctness. Fixing a verified bug inside the
browser extractor — a dead endpoint call, a section whose rows are never read — is in scope.
What is out of scope is folding the two methods together or replacing one with the other.

Both must ask, never assume: which school, then credentials (Bitwarden or typed in), then how much detail. Prompts in plain Hindi ("Kaunsi school ka data chahiye?", "Kitna detail chahiye?") — no technical jargon.

### Pitfalls

- **List API has no full address.** `/teacher/viewTeacher` returns only `cVillage` / `pVillage`. `esk_teacher_list.py` must call `/teacher/registrationInfo` per teacher to build the combined address cell (house, street, panchayat, village, PIN, district, block, state).
- **openpyxl cannot write list/dict cell values** — `ValueError: Cannot convert [...] to Excel`. `json.dumps` any list/dict before `ws.append()`.
- `esk_teacher_detail_extract.py` requires `ESHIKSHAKOSH_TARGET_UDISE` in the environment and refuses to guess.
- Bitwarden returns 429 Too Many Requests — wait ~65s before retrying.

### API endpoints for detail extraction

All read-only POSTs. Verified live; every endpoint below returns HTTP 200.

| Endpoint | Key | Returns |
|---|---|---|
| `/teacher/registrationInfo` | `encId` | `data` dict, 55 fields — readable labels, masked identifiers |
| `/teacher/viewTeacherEducationInfo` | `encId` | `preServicedata` **and** `inServicedata` |
| `/teacher/viewTeacherProfessionalInfo` | `encId` | `data` list |
| `/teacher/viewTeacherOtherInfo` | `encId` | `data` list |
| `/teacher/viewTeacherTrainingInfo` | `encId` | `data` list |
| `/teacher/getExistingServiceInfo` | `teacherEncryptedId` | `serviceInfo` list |

Do NOT call `/teacher/getTeacherDetails`. It returns HTTP 500 `{"message": "Server Error"}`
for every key tried (`teacherId`, `encId`, `tId`, `teacherEncryptedId`, `id`). It was removed
from `DETAIL_ENDPOINTS`; re-adding it burns a request per teacher and pollutes the section
error map with noise.

### PITFALL — a section's rows live under a section-specific key

Never assume every section returns its rows under `data`. Read the real key:

| Section | Row key |
|---|---|
| educationInfo | `preServicedata` + `inServicedata` (two separate lists) |
| professionalInfo / otherInfo / trainingInfo | `data` |
| serviceInfo | `serviceInfo` |

A generic row extractor that only looks for `serviceInfo` / `educationInfo` / `data` silently
returns zero rows for Education, so the sheet prints `No records for this school` while the
portal holds records. `No records` is a claim about your parser, not about the portal —
confirm against the live endpoint before believing an empty section. Merge the two education
lists and tag each row (`_serviceType` = `Pre-Service` / `In-Service`) so the distinction
survives into the workbook.

**Pitfall**: Issue every detail call through the live browser session so the portal's own auth headers apply. A plain `requests` session gets HTTP 401.

`scripts/verify_endpoints.py` walks every endpoint above against one UDISE and prints HTTP
status plus row count per section. Run it before believing an empty sheet, and after any
portal change — it is what distinguishes a dead endpoint from a parser that reads the wrong
key.

### Output sheets (full detail mode)

| Sheet | Rows | Cols | Content |
|---|---|---|---|
| Teachers | N+1 | 28 | Basic roster |
| Registration Info | N+1 | 55 | Personal, address, family, IDs |
| Education | varies | varies | Qualifications (may be empty) |
| Professional | varies | varies | Professional qualifications |
| Other Info | varies | varies | Other details |
| Training | varies | varies | Training & language |
| Service History | varies | varies | Posting history |

A section with genuinely no records says `No records for this school`.

## Field labels — list API vs registrationInfo

The teacher-list endpoint (`/teacher/viewTeacher`) returns **raw numeric codes** for
`gender`, `maritalStatus`, `natureOfAppointmt`, `classCategory`, `socialCategory`,
`appointedSubject`, and returns district/block as codes. It is the only endpoint that
returns **unmasked** `mobile`, `panNo`, `aadhaarNo`.

`/teacher/registrationInfo` returns those same fields as **readable labels** (`Male`,
`Single`, `School Teacher (BPSC)`, `GT (9-10)`, `General`, `Science (विज्ञान)`) and
district/block as names — but it **masks** `mobile` (`XXXXXXX594`), `panNo`
(`XXX-XXX-323K`) and `aadhaarNo` (`XXXX-XXXX-6807`).

Rule: when an export needs readable values, fetch both and merge — labels from
`registrationInfo`, unmasked identifiers from the list API. Never take mobile/PAN/Aadhaar
from `registrationInfo`; never ship raw codes when the label is available.

`gpfNo` / `uanNo` are `None` in the list API and `--` in `registrationInfo` — genuinely
absent in the portal, so write a blank cell, not the string `None`.

## Legacy Script

```
~/projects/eshikshakosh-automation/modules/teacher/scripts/esk_teacher_extract.py
```

See `references/api-technical.md` for full field list, auth header mapping, and common errors.

Supporting scripts:
- `esk_teacher_intercept.py` — intercepts browser API calls to discover payload structure
- `esk_teacher_probe.py` — probes teacher API response structure

## Repository documentation moves with the code

`~/projects/eshikshakosh-automation` carries a documentation layer the user expects to match
the code after any behaviour change. Update all of it in the same commit:

| File | What it carries |
|---|---|
| `README.md` | top-level workflow, verified endpoint contract |
| `TEACHER_REPORT.md` | export shapes, credential paths, security scope |
| `modules/teacher/TEACHER_SCRIPTS.md` | script inventory, supported vs archived, review findings |
| `.ai/CURRENT-STATE.md`, `docs/current-status.md` | what is verified right now |
| `docs/HISTORY.md`, `docs/MEMORY.md` | dated change log, durable project facts |
| `TASKS.md`, `PRD.md`, `brain/eshikshakosh-report/*` | task state and handoff context |
| `skills/eshikshakosh-teacher/SKILL.md` | repo copy — keep byte-identical to the installed Hermes skill |

After moving or deleting a script, grep every doc for its old path and for every endpoint
name you changed — retired files and dead endpoints linger in READMEs long after the code has
moved. Never commit workbooks, credentials or tokens: `*.xlsx` and `*.bak*` are gitignored,
but confirm with `git diff --cached --name-only` before committing.

## Authorization guard

Teacher data contains PII (Aadhaar, PAN, mobile, email). Export only to authorized requester in private chat. Do not send to groups.

## Relationship to eshikshakosh-report

`eshikshakosh-report` covers **student** OTR reports only. This skill covers **teacher** data extraction. They share the same portal but use different APIs, payloads, and auth patterns. Do not mix them up.