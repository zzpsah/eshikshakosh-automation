# e-ShikshaKosh Automation

Private, read-only automation for student OTR and teacher reports. The repository is organized by functional module so future modules can be added without mixing scripts.

## Modules

| Module | Purpose | Entry point | Documentation |
|---|---|---|---|
| Student | Student OTR exports and preserved Colab notebooks | `modules/student/run_report.sh` (VPS launcher: `~/.local/bin/eshikshakosh-report`) | [Student README](modules/student/README.md) |
| Teacher | Teacher roster and full-profile exports | `modules/teacher/run_teacher_report.sh`, `modules/teacher/run_teacher_detail_report.sh` | [Teacher README](modules/teacher/README.md) · [Script inventory](modules/teacher/TEACHER_SCRIPTS.md) |
| Shared | School registry, credential wrapper config, common support files | `shared/` | [VPS path map](docs/VPS-PATHS.md) |
| Web portal | Vercel Next.js command guide (not yet a report backend) | `web/` | [Web README](web/README.md) |

## Oracle VPS canonical paths

Repository: `/home/prashant/projects/eshikshakosh-automation` (`~/projects/eshikshakosh-automation`).

- Student code and notebook files: `modules/student/`
- Teacher code and teacher reports: `modules/teacher/`
- Shared school registry/config: `shared/`
- Private student launcher: `/home/prashant/.local/bin/eshikshakosh-report`
- Protected secret wrapper: `/home/prashant/.local/bin/eshikshakosh-run`
- Python environment: `/home/prashant/projects/eshikshakosh-automation/.venv/`
- Teacher workbook exports: `/home/prashant/exports/`
- Current student runner writes `Student_Details_*.xlsx` to the repository root. Existing generated workbooks are private operational data, not source files.
- Vercel project files: `web/`; local `.vercel/` metadata must not be committed.

See [docs/VPS-PATHS.md](docs/VPS-PATHS.md) for the full path map and how to add future modules.

## Safety

All maintained report workflows are read-only against e-ShikshaKosh. Do not commit credentials, tokens, student/teacher personal data, exported workbooks, or screenshots. Secrets must be supplied by the existing protected runtime. Full exports may contain unmasked identifiers; keep them private and share only via authorised channels.

## Useful commands

```bash
cd ~/projects/eshikshakosh-automation
modules/teacher/run_teacher_report.sh --list
modules/teacher/run_teacher_report.sh --school Sahaspur
modules/teacher/run_teacher_detail_report.sh --school Sahaspur
~/.local/bin/eshikshakosh-report --class 10 --mode masked
```

For a teacher-detail smoke test, set `ESHIKSHAKOSH_DETAIL_LIMIT=2` before invoking the detail runner. Avoid full live exports for routine path checks.

## Other project documentation

- [Architecture](docs/ARCHITECTURE.md) · [Commands](docs/COMMANDS.md) · [Security](docs/SECURITY.md) · [Test plan](docs/TEST_PLAN.md)
- [Project requirements](PRD.md) · [Development rules](RULES.md) · [Tasks](TASKS.md)
- [Student report documentation](modules/student/README.md) · [Teacher report documentation](modules/teacher/README.md)
