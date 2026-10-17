# Teacher Extraction Scripts — Inventory and Safe Usage

Last reviewed: 2026-10-17 (Oracle VPS)

This file maps the e-ShikshaKosh teacher-report workflow. It is separate from the student OTR workflow documented in `READ_ME_FIRST.txt`.

## Supported entry points

Use these two runners for normal work. Both use the school registry and protected credential flow.

| Purpose | Runner | Python target | Output |
|---|---|---|---|
| Teacher roster / standard list export | `run_teacher_report.sh` | `esk_teacher_browser_extract_school.py` | Timestamped Excel in `~/exports` |
| Full teacher profile export | `run_teacher_detail_report.sh` | `esk_teacher_detail_extract.py` | Seven-sheet timestamped Excel in `~/exports` |

Commands from the repository root:

```bash
local-script/run_teacher_report.sh --list
local-script/run_teacher_report.sh --school Sahaspur
local-script/run_teacher_detail_report.sh --school Sahaspur

# Safe small detail smoke test (only two teachers)
ESHIKSHAKOSH_DETAIL_LIMIT=2 local-script/run_teacher_detail_report.sh --school Sahaspur
```

For one-time credentials, follow the runner's usage comments. Never put real passwords into documentation, shell history, source files, or Git.

### Direct scripts (no runner)

Both can also be launched straight through the protected wrapper, which is how the API list
export is normally run:

```bash
ESHIKSHAKOSH_TARGET_UDISE=10160203806 \
  ~/.local/bin/eshikshakosh-run .venv/bin/python3 local-script/esk_teacher_list.py

ESHIKSHAKOSH_TARGET_UDISE=10160203806 \
  ~/.local/bin/eshikshakosh-run .venv/bin/python3 local-script/esk_teacher_detail_extract.py
```

`ESHIKSHAKOSH_TARGET_UDISE` is mandatory for both. Neither script has a default school.

## Python files and their roles

| File | Role | Status / guidance |
|---|---|---|
| `esk_teacher_list.py` | API-based 28-column roster: list endpoint + per-teacher `registrationInfo` for readable labels and the combined address cell | **Canonical API list export.** Direct launch only; not wired to a runner |
| `esk_teacher_browser_extract_school.py` | School-agnostic roster extractor; derives school scope and auth context from the live browser request | **Canonical browser roster extractor**; called by `run_teacher_report.sh` |
| `esk_teacher_detail_extract.py` | Reads registration, education, professional, other, training and service-history sections through the authenticated browser session | **Canonical detail extractor**; called by `run_teacher_detail_report.sh` |
| `esk_code_maps.py` | Loads/saves verified code-to-label mappings learned from portal service-history data | Tracked and committed; imported by the canonical extractors |
| `esk_code_maps.json` | Persisted learned label mappings | Tracked and committed. Runtime support data — never insert personal data or credentials |
| `esk_schools.py` | School alias, UDISE and Bitwarden-key registry | Shared configuration for both runners |
| `esk_teacher_extract.py` | Older list/API implementation and Excel field/header mapping used by the legacy Tetahali-specific extractor | **Legacy/reference**; not a supported runner target |
| `esk_teacher_browser_extract.py` | Older Tetahali-specific browser extractor; hardcodes UDISE `10160203806` and school ID `42645`; contains an older full-detail path | **Do not use for Sahaspur or other schools** |

## Archived experiments

The following files are under `local-script/archive/` and are historical reference, not supported entry points:

- `esk_teacher_api.py`
- `esk_teacher_intercept.py`
- `esk_teacher_playwright.py`
- `esk_teacher_probe.py`
- `esk_teacher_detail_intercept.py`
- `esk_teacher_detail_values.py`
- `esk_teacher_edu_probe.py`
- `esk_teacher_mapping_extract.py`
- `install-hermes-skill.sh`, `telegram_report_test.sh` — retired shell wrappers

`local-script/run_report.sh` is **not** archived: it is the live student-report runner that
`~/.local/bin/eshikshakosh-report` executes. It was briefly moved into `archive/` on
2026-10-17 and that broke the student export path; it has been restored to `local-script/`
and its `APP` path repointed at `student-scripts/esk_otr_api.py`.

The experimental `esk_teacher_unified.py` (a proposed one-script list + detail implementation)
was **deleted on 2026-10-17** at the user's direction. Do not recreate it: the API list and the
browser detail extractor stay separate.

Timestamped backup copies (for example `*.bak_*`) are snapshots, not entry points.

## Data flow

```text
run_teacher_report.sh
  -> esk_schools.py (resolve school + Bitwarden secret keys)
  -> protected secret wrapper
  -> Playwright login and live browser request capture
  -> esk_teacher_browser_extract_school.py
  -> esk_code_maps.py (verified display labels)
  -> roster workbook in ~/exports

esk_teacher_list.py (direct)
  -> protected secret wrapper -> Playwright login
  -> /teacher/viewTeacher (codes, unmasked mobile/PAN/Aadhaar)
  -> /teacher/registrationInfo per teacher (labels, combined address)
  -> merged 28-column roster workbook in ~/exports

run_teacher_detail_report.sh
  -> same school/credential resolution
  -> esk_teacher_detail_extract.py (authenticated browser session)
  -> esk_code_maps.py (verified display labels)
  -> roster + registration + education + professional + other + training
     + service-history workbook in ~/exports
```

The supported workflows are read-only against the portal. Workbook creation and learned
mapping updates are local filesystem writes. Detail API requests must remain in the
authenticated browser session because separate direct HTTP requests have returned HTTP 401.

## Verified endpoint contract — 2026-10-17

Every endpoint below was called live against UMV Tetahali on 2026-10-17.

| Endpoint | Key | HTTP | Returns |
|---|---|---|---|
| `/teacher/viewTeacher` | `schoolUdiseCode` | 200 | roster page |
| `/teacher/registrationInfo` | `encId` | 200 | `data` dict, 55 fields, readable labels, masked identifiers |
| `/teacher/viewTeacherEducationInfo` | `encId` | 200 | `preServicedata` **and** `inServicedata` |
| `/teacher/viewTeacherProfessionalInfo` | `encId` | 200 | `data` list |
| `/teacher/viewTeacherOtherInfo` | `encId` | 200 | `data` list |
| `/teacher/viewTeacherTrainingInfo` | `encId` | 200 | `data` list |
| `/teacher/getExistingServiceInfo` | `teacherEncryptedId` | 200 | `serviceInfo` list |
| ~~`/teacher/getTeacherDetails`~~ | any | **500** | `{"message": "Server Error"}` — **removed from the extractor** |

`/teacher/getTeacherDetails` was tried with `teacherId`, `encId`, `tId`,
`teacherEncryptedId` and `id`. All five returned HTTP 500. It contributed nothing and has
been deleted from `DETAIL_ENDPOINTS`. Do not re-add it.

### Code labels vs masked identifiers

The list endpoint returns raw numeric codes for `gender`, `maritalStatus`,
`natureOfAppointmt`, `classCategory`, `socialCategory`, `appointedSubject` and returns
district/block as codes. It is the only endpoint that returns **unmasked** `mobile`, `panNo`
and `aadhaarNo`.

`/teacher/registrationInfo` returns those fields as readable labels (`Male`, `Single`,
`School Teacher (BPSC)`, `GT (9-10)`, `General`, `Science (विज्ञान)`) and district/block as
names — but masks `mobile` (`XXXXXXX594`), `panNo` (`XXX-XXX-323K`) and `aadhaarNo`
(`XXXX-XXXX-6807`).

`esk_teacher_list.py` therefore merges both: labels from `registrationInfo`, unmasked
identifiers from the list endpoint. Never take mobile/PAN/Aadhaar from `registrationInfo`,
and never ship raw codes when the label is available.

`gpfNo` / `uanNo` are `None` in the list endpoint and `--` in `registrationInfo` — genuinely
absent in the portal. Write a blank cell, not the string `None`.

## Review findings

1. The supported runner contract has **two runner scripts** and **two canonical browser extractor targets**, plus the school registry and the API list script.
2. `esk_teacher_unified.py` was removed on 2026-10-17. Keep the two methods separate — this is an explicit user directive.
3. `esk_teacher_browser_extract.py` hardcodes Tetahali's UDISE and numeric school ID. It must not be used for Sahaspur.
4. `esk_code_maps.py` and `esk_code_maps.json` are now tracked and committed; the earlier "uncommitted worktree helper" caveat no longer applies.
5. **Education data was being silently dropped.** `/teacher/viewTeacherEducationInfo` returns two separate lists (`preServicedata`, `inServicedata`), but `_rows()` only looked for `serviceInfo` / `educationInfo` / `data`. The Education sheet therefore printed `No records for this school` even when the portal held records. Fixed 2026-10-17: both lists are now tagged (`_serviceType` = `Pre-Service` / `In-Service`) and merged. Verified on UMV Tetahali: 16 pre-service + 1 in-service rows across 4 teachers, where the sheet previously showed none.
6. A detail sheet that says `No records for this school` means the extractor received no rows for that category. By itself it does not prove the portal has no data — check the endpoint response and status first.
7. Generated workbooks contain personal and employment information. Keep them in `~/exports`, preserve restrictive permissions, and never commit them.

## Validation performed

- Confirmed both runner-to-extractor paths by reading the shell scripts.
- Confirmed both canonical extractors import the shared code-mapping helper.
- Confirmed the detail extractor requires an explicit target UDISE and documents the read-only detail endpoints.
- Called all seven detail endpoints plus the dead `/teacher/getTeacherDetails` live on 2026-10-17 and recorded HTTP status and row counts.
- Ran the detail extractor end to end after the Education fix: 16 teachers, 6 sections each, Education sheet 18 rows.
- Ran shell syntax checks and Python compilation for the supported runners/extractors.
- No portal write, credential access beyond the protected wrapper, or source-file cleanup was performed.
