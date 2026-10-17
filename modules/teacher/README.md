# Teacher module

Canonical VPS directory: `~/projects/eshikshakosh-automation/modules/teacher/`.

- `run_teacher_report.sh` → `scripts/esk_teacher_browser_extract_school.py`: school-scoped roster export.
- `run_teacher_detail_report.sh` → `scripts/esk_teacher_detail_extract.py`: seven-sheet full profile.
- `scripts/esk_teacher_list.py`: API-based 28-column roster, direct use requires the protected wrapper and explicit target UDISE.
- `scripts/esk_teacher_extract.py`: shared legacy field/header mapping imported by browser extractors.
- `scripts/esk_code_maps.py` + `scripts/esk_code_maps.json`: verified label mappings.
- `scripts/generate_teacher_pdf.py`: legacy/experimental, not a canonical runner.
- `archive/`: retired probes and snapshots, not production entry points.
- `TEACHER_SCRIPTS.md`: complete script inventory, endpoint contracts, safety and validation notes.

## Actual Oracle VPS paths

| Purpose | Path |
|---|---|
| Repository | `/home/prashant/projects/eshikshakosh-automation` |
| Roster runner | `modules/teacher/run_teacher_report.sh` |
| Detail runner | `modules/teacher/run_teacher_detail_report.sh` |
| Extractors | `modules/teacher/scripts/` |
| School/credential-key registry | `shared/esk_schools.py` |
| Secret wrapper | `/home/prashant/.local/bin/eshikshakosh-run` |
| Output directory | `/home/prashant/exports/` |

```bash
modules/teacher/run_teacher_report.sh --list
modules/teacher/run_teacher_report.sh --school Sahaspur
modules/teacher/run_teacher_detail_report.sh --school Sahaspur
ESHIKSHAKOSH_DETAIL_LIMIT=2 modules/teacher/run_teacher_detail_report.sh --school Sahaspur
```

Teacher exports are read-only portal reads but contain personal/employment data. Never commit workbooks. Add future teacher functionality here; only cross-module utilities belong in `shared/`.
