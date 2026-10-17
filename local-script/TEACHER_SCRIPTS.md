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

## Python files and their roles

| File | Role | Status / guidance |
|---|---|---|
| `esk_teacher_browser_extract_school.py` | School-agnostic roster extractor; derives school scope and auth context from the live browser request | **Canonical roster extractor**; called by `run_teacher_report.sh` |
| `esk_teacher_detail_extract.py` | Reads registration, education, professional, other, training and service-history sections through the authenticated browser session | **Canonical detail extractor**; called by `run_teacher_detail_report.sh` |
| `esk_code_maps.py` | Loads/saves verified code-to-label mappings learned from portal service-history data | **Working-tree helper** imported by the locally modified canonical extractors; the helper and related extractor edits were not included in the documentation/portal commit, so review and commit them together before relying on this change from a clean checkout |
| `esk_code_maps.json` | Persisted learned label mappings | Working-tree runtime/support data; untracked during this review. Inspect changes before committing, and never insert personal data or credentials |
| `esk_schools.py` | School alias, UDISE and Bitwarden-key registry | Shared configuration for both runners |
| `esk_teacher_extract.py` | Older list/API implementation and Excel field/header mapping used by the legacy Tetahali-specific extractor | **Legacy/reference**; not the supported runner target. Working-tree changes were left untouched |
| `esk_teacher_browser_extract.py` | Older Tetahali-specific browser extractor; hardcodes UDISE `10160203806` and school ID `42645`; contains an older full-detail path | **Do not use for Sahaspur or other schools.** Working-tree changes were left untouched |
| `esk_teacher_unified.py` | Separate proposed one-script list + detail implementation | **Not wired to either supported runner.** Treat as experimental until its behaviour and tests are reviewed; avoid maintaining two production paths |
| `esk_teacher_detail_intercept.py` | Exploratory click/API interception probe | Diagnostic only; not called by supported runners |
| `esk_teacher_edu_probe.py` | Exploratory education-endpoint probe | Diagnostic only. Attempts direct `requests` calls and prints token prefixes; do not use for routine exports |
| `esk_teacher_mapping_extract.py` | Exploratory dropdown/code mapping capture with hardcoded school mapping | Diagnostic only; not called by supported runners |
| `esk_teacher_detail_values.py` | Older single-teacher form-field extraction experiment | Diagnostic/legacy only; not called by supported runners |

## Archived experiments

The following files are under `local-script/archive/` and are historical reference, not supported entry points:

- `esk_teacher_api.py`
- `esk_teacher_intercept.py`
- `esk_teacher_playwright.py`
- `esk_teacher_probe.py`

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

run_teacher_detail_report.sh
  -> same school/credential resolution
  -> esk_teacher_detail_extract.py (authenticated browser session)
  -> esk_code_maps.py (verified display labels)
  -> roster + registration + education + professional + other + training
     + service-history workbook in ~/exports
```

The two supported workflows are intended to be read-only against the portal. Workbook creation and learned mapping updates are local filesystem writes. Detail API requests must remain in the authenticated browser session because separate direct HTTP requests have returned HTTP 401.

## Review findings

1. The supported runner contract has **two runner scripts** and **two canonical extractor targets**, plus the school registry. The mapping helper is present in the current worktree but its integration is still uncommitted.
2. Four archived scripts and four standalone diagnostic/legacy probes remain outside the supported path; `esk_teacher_unified.py` is an additional experimental candidate, not yet wired into the runners.
3. `esk_teacher_browser_extract.py` hardcodes Tetahali's UDISE and numeric school ID. It must not be used for Sahaspur.
4. The working tree already had changes to `esk_teacher_extract.py` and `esk_teacher_browser_extract.py`; additional files for code mappings and a unified extractor appeared during the review. These files were not reverted, deleted, or wired into the runner during this documentation pass, to avoid disrupting another session's work. The code-map helper and JSON are still untracked, and the two extractor edits are still uncommitted; the last documentation/portal commit therefore does not include that source-code change set.
5. A detail sheet that says `No records for this school` means the extractor received no rows for that category. By itself, it does not prove the portal has no data; check the endpoint response and status before making that conclusion.
6. Generated workbooks contain personal and employment information. Keep them in `~/exports`, preserve restrictive permissions, and never commit them.

## Validation performed

- Confirmed both runner-to-extractor paths by reading the shell scripts.
- Confirmed both canonical extractors import the shared code-mapping helper.
- Confirmed the detail extractor requires an explicit target UDISE and documents the seven read-only detail endpoints.
- Ran shell syntax checks and Python compilation for the supported runners/extractors during the review.
- No portal write, live teacher export, credential access, or source-file cleanup was performed.
