# Project History

## Initial maintained flow
- Safe command-line/Colab path built around short-lived Bearer-token input and masked exports.

## 2026-09-27 local/VPS integration
- Repo-local virtual environment adopted.
- Playwright and `nest_asyncio` added for the local workflow.
- Bitwarden-backed credential injection verified.
- Local report runner and Hermes skill installed.
- Real current-session workbook generation verified.
- Apr-Mar automatic session selection added.
- Hermes routing constrained to the verified report runner.
- Same-channel Telegram/WhatsApp file delivery remained pending verification.
- Internal prompt/tool-trace echo behavior was investigated in Hermes messaging sessions.
- DevOS Vibe Coding baseline and project-specific documentation layer populated.

## 2026-10-02 repository reconciliation
- Reviewed the previously dirty Oracle working tree.
- Retained executable-bit fixes for `local-script/install-hermes-skill.sh` and `local-script/run_report.sh`.
- Removed an untracked guessed teacher-API placeholder rather than committing unverified endpoints.
- Repaired the missing opening module docstring in the safe root exporter.
- Removed a generated Student OTR workbook from the current Git tree while preserving the local ignored artifact.
- Added project-specific `brain/eshikshakosh-report/` recovery/state documentation.
- Local shell syntax, Python compile, CLI-help and `git diff --check` validation passed.

## 2026-10-03 — Scoped reports and WhatsApp delivery verified

Completed the scoped report update: class/section/stream API filters, split-sheet output, flag-based launcher, and skill v2.4.0. A real Class 10 masked run returned 34 students and passed workbook masking checks. The resulting Excel file was delivered successfully to the configured WhatsApp Home/Admin chat, closing the previous same-channel WhatsApp verification task.


## 2026-10-03 — Natural-language messaging v2.5

- Identified two simultaneously active Hermes e-ShikshaKosh skills; the older `eshikshakosh-report` v2.1.0 was still selected frequently.
- Synchronized the legacy and current installed skills to v2.5 behavior.
- Added Hindi/Hinglish natural-language intent handling and spelling-tolerant report phrasing.
- Removed redundant approval/continue prompts for clear read-only report generation and same-private-chat delivery.
- Local Hermes parsing regression passed without invoking report tools.
- Repository update prepared for commit after local regression checks; real inbound natural-language WhatsApp regression remains a separate follow-up.
