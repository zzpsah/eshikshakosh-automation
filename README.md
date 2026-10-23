# e-ShikshaKosh Automation

Private, read-only automation for student OTR and teacher reports. The repository is organized by functional module so future modules can be added without mixing scripts.

**Start here for the web app:** [`docs/HANDOFF-WEB-CONNECTIVITY.md`](docs/HANDOFF-WEB-CONNECTIVITY.md) — the Vercel app, the VPS gateway and job service, the Tailscale funnel path, and every full path. It supersedes the older architecture/deployment docs.

## Modules

| Module | Purpose | Entry point | Documentation |
|---|---|---|---|
| Student | Student OTR exports and preserved Colab notebooks | `modules/student/run_report.sh` (VPS launcher: `~/.local/bin/eshikshakosh-report`) | [Student README](modules/student/README.md) |
| Teacher | Teacher roster and full-profile exports | `modules/teacher/run_teacher_report.sh`, `modules/teacher/run_teacher_detail_report.sh` | [Teacher README](modules/teacher/README.md) · [Script inventory](modules/teacher/TEACHER_SCRIPTS.md) |
| Shared | School registry, credential wrapper config, common support files | `shared/` | [VPS path map](docs/VPS-PATHS.md) |
| Web portal | Report workbench (Next.js) backed by the VPS gateway + job service | `web/` | [Handoff — connectivity & paths](docs/HANDOFF-WEB-CONNECTIVITY.md) · [Web README](web/README.md) |

## Oracle VPS canonical paths

Repository: `/home/prashant/projects/eshikshakosh-automation` (`~/projects/eshikshakosh-automation`).

- Student code and notebook files: `modules/student/`
- Teacher code and teacher reports: `modules/teacher/`
- Shared school registry/config: `shared/`
- Private student launcher: `/home/prashant/.local/bin/eshikshakosh-report`
- Protected secret wrapper: `/home/prashant/.local/bin/eshikshakosh-run`
- Python environment: `/home/prashant/projects/eshikshakosh-automation/.venv/`
- Teacher workbook exports: `/home/prashant/exports/`
- Student runner moves completed `Student_Details_*.xlsx` files to `/home/prashant/exports/student/`; historical reports are kept in its `archive/` subfolder. Workbooks are private operational data, not source files.
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

## Cross-project AI handoff

For cross-repository ownership, shared infrastructure dependencies, and safe AI handoff rules, start with the [Oracle VPS cross-project map](https://github.com/zzpsah/oracle-server/blob/main/docs/CROSS-PROJECT-MAP.md). Then follow this repository’s own AGENTS.md, architecture, current-state, security, and test documentation. The map is navigation guidance, not a substitute for verifying live state.
