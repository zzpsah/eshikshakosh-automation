# Oracle VPS path map and module conventions

Last reviewed: 2026-10-17. Canonical host: `oracle-server`; Linux user: `prashant`.

## Repository layout

| Path on Oracle VPS | Purpose |
|---|---|
| `/home/prashant/projects/eshikshakosh-automation/` | Git repository root; `~/projects/eshikshakosh-automation` |
| `modules/student/` | All student report scripts, runner, docs and notebooks |
| `modules/teacher/` | All teacher report scripts, runners, docs and retired teacher experiments |
| `shared/` | Shared school registry, wrapper configuration and truly cross-module helpers |
| `web/` | Next.js frontend for the Vercel workflow/command guide |
| `skills/eshikshakosh-otr/` | Hermes student workflow instructions |
| `skills/eshikshakosh-teacher/` | Hermes teacher workflow instructions |
| `docs/` | Cross-module architecture, commands, security, testing and this path map |
| `brain/eshikshakosh-report/` | Recovery/handoff notes for the project |
| `.venv/` | Shared Python virtual environment; not committed |
| `.git/` | Repository metadata |

## External runtime paths

| Path | Purpose / current behavior |
|---|---|
| `/home/prashant/.local/bin/eshikshakosh-report` | User-facing student report launcher; invokes `modules/student/run_report.sh` |
| `/home/prashant/.local/bin/eshikshakosh-run` | Protected secret-injection wrapper |
| `/home/prashant/.local/bin/secret-run` | Lower-level secret runtime invoked by wrapper |
| `/home/prashant/exports/` | Teacher report output directory by default |
| Repository root `Student_Details_*.xlsx` | Student runner currently writes/locates generated workbook here |
| `/home/prashant/.local/share/` and user runtime paths | Do not move/modify unless separately inspected; not module source |
| Vercel project root `web/` | Frontend deployment; `.vercel/` remains local/ignored |

## Entry points

```bash
cd ~/projects/eshikshakosh-automation
# Student: wrapper/launcher resolves secrets; never call with passwords in shell history
~/.local/bin/eshikshakosh-report --class 10 --mode masked
# Teacher roster and profile
modules/teacher/run_teacher_report.sh --list
modules/teacher/run_teacher_report.sh --school Sahaspur
modules/teacher/run_teacher_detail_report.sh --school Sahaspur
# Static checks only; no portal login required
bash -n modules/student/run_report.sh modules/teacher/run_teacher_report.sh modules/teacher/run_teacher_detail_report.sh
```

## Module boundaries

- **Student-only files** stay in `modules/student/`, including both `.ipynb` files. Do not delete or overwrite `Eshikshakosh_OTR_ORIGINAL.ipynb`.
- **Teacher-only files** stay in `modules/teacher/`. The canonical production paths are the two module runners and their documented extractors; archived probes are not to be invoked.
- **Shared files** belong in `shared/` only if both modules need them. `shared/esk_schools.py` is the current school/credential-key registry.
- Add a future feature as `modules/<new-module>/` with a README, scripts, runner, tests and data-flow documentation. Do not create another flat root-level script collection.
- Root `README.md` is the navigation index; module README files own module-specific instructions; `docs/VPS-PATHS.md` owns this physical path map. Update these documents in the same change as any move.

## Data and safety

Generated workbooks are private operational outputs, not source. Never commit `.xlsx`, credentials, tokens, cookies, student/teacher personal data, or screenshots. The repository ignores workbooks and local environment files. Do not move runtime secrets or external launchers merely to make the Git tree look tidy.
