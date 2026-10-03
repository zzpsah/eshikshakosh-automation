# e-ShikshaKosh Report Automation — Current State

Last verified: 2026-10-02.

- Branch: main.
- Root safe exporter syntax repaired.
- Local report runner scripts are executable.
- `local-script/esk_otr_api.py --help` passes in the project virtualenv.
- Shell syntax checks pass for `install-hermes-skill.sh` and `run_report.sh`.
- Generated Student OTR workbook was removed from current Git tracking while preserving the local file.
- `*.xlsx` is ignored by Git.
- Unverified guessed teacher API placeholder was removed and not committed.
- Portal-changing operations are not part of this project.

## Command UX and export mode — 2026-10-02

- Canonical slash command: `/eshikshakosh`.
- Aliases: `/esk`, `/esk-report`, `/eshikshakosh-report`, `/eshikakossh-report`.
- No-argument command asks for school name.
- Known school aliases resolve to stored Bitwarden credentials when the pair exists.
- Missing credentials route to secure `/bw add` rather than password-in-chat.
- Export modes: `full` / `masked`; default **`full`**.

## Scoped reports — 2026-10-03

- Private launcher supports `--class`, `--section`, `--stream`, `--split-sheets`, `--mode`, and `--year`.
- Filtered requests are applied at the existing read-only student-list API request.
- Split-sheet output groups Classes 9–10 by class+section and Classes 11–12 by class+section+stream.
- Skill v2.4.0 documents natural-language scope conversation.
