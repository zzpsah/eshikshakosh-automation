# Product Requirements Document

## Product
e-ShikshaKosh Student Details Automation.

## Goal
Generate an authorized, read-only student-details Excel workbook from e-ShikshaKosh, with safe credential handling and same-channel delivery through Hermes where available.

## Primary workflows
1. Safe manual/Colab flow using a short-lived Bearer token and masked export.
2. Local/VPS flow using Playwright/API automation and Bitwarden-backed credential injection for an authorized known school.

## Current verified local state
- Repository-local virtual environment is used.
- Playwright is installed and verified.
- `local-script/esk_otr_api.py` generated a real workbook successfully for the current academic session.
- Verified run summary: 220 total students, 2 OTR registered, 218 OTR pending, 219 Aadhaar values present, 220 bank accounts, 220 mother names.
- Current academic session is derived automatically using an April-March boundary unless explicitly overridden.
- Hermes is instructed to use `~/.local/bin/eshikshakosh-report` and not improvise generic browser/teacher-data scraping.
- Same-channel Telegram/WhatsApp attachment delivery is still pending end-to-end verification.

## Core requirements
- Portal access remains read-only; no submit/edit/certify/delete behavior.
- Credentials are injected at runtime and never printed.
- Generated unmasked workbooks remain private and are never committed to Git.
- Authorized private chats only for unmasked workbook delivery.
- Known school credentials may be resolved through the verified Bitwarden launcher.
- Unknown-school credentials are one-time only unless separately approved for storage.
- Report generation must end with a real file path such as `REPORT_READY=<path>`; browser navigation alone is not success.

## Planned improvements
- Rename workbook output from OTR-specific naming to a generic Student Details naming pattern.
- Add a private multi-school registry/credential mapping.
- Prove Telegram and WhatsApp same-channel file delivery.
- Harden Hermes messaging against internal prompt/tool-trace leakage.

## Out of scope
- Portal data mutation.
- Storing student workbooks, passwords, tokens, cookies, or private exports in Git.
- Sending unmasked data to unauthorized users or groups.
