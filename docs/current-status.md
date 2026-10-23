# Current Status

> **Superseded.** Verified state as of 2026-10-23 is in
> [`docs/HANDOFF-WEB-CONNECTIVITY.md`](HANDOFF-WEB-CONNECTIVITY.md), including
> the live service list, ports and known gaps.

Verified 2026-10-17.

- Root safe exporter repaired and compiles.
- Private local API runner compiles and exposes expected CLI arguments.
- Hermes/local shell wrappers pass syntax checks and are executable.
- Generated workbooks are ignored and no longer tracked in the current tree.
- Guessed teacher API placeholder removed.
- No live portal mutation performed.
- Canonical Vibe handoff: `brain/eshikshakosh-report/`.

## Teacher export (2026-10-17)

- `modules/teacher/scripts/esk_teacher_list.py` — API-based 28-column roster, readable labels, combined
  address. Verified live: 16 teachers at UMV Tetahali.
- `modules/teacher/scripts/esk_teacher_detail_extract.py` — browser-based 7-sheet profile. Verified live:
  16 teachers, 6 sections each.
- All seven detail endpoints return HTTP 200. `/teacher/getTeacherDetails` returns HTTP 500 and
  was removed from the extractor.
- Education sheet data-loss bug fixed (`preServicedata` + `inServicedata` were never read):
  2 rows → 18 rows on the same school.
- `esk_teacher_unified.py` deleted; API list and browser detail methods stay separate.
- Retired scripts moved to `modules/student/scripts/` and `modules/teacher/archive/`; README paths updated.