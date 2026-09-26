---
name: eshikshakosh-otr
description: Generate a private read-only e-ShikshaKosh OTR Excel report and return it to the requesting Telegram or WhatsApp chat.
version: 2.0.0
author: zzpsah, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [eshikshakosh, bihar, student-report, excel, otr, telegram, whatsapp]
    related_skills: []
---

# e-ShikshaKosh OTR Report

Use this skill when an authorized user asks for an e-ShikshaKosh report from Telegram or WhatsApp.

## Core behavior

1. Keep the workflow read-only. Never submit, edit, certify, delete, or update portal data.
2. Reply in the same channel where the request arrived:
   - Telegram request -> Telegram document reply
   - WhatsApp request -> WhatsApp document reply
3. Ask for the school name first if it is not already clear.
4. For a known school with stored Bitwarden credentials, use the stored credentials through the verified `eshikshakosh-run` launcher.
5. For an unknown school, ask for the portal user ID / UDISE and a one-time password. Do not store that password in memory, Git, logs, or a config file.
6. Default academic year to `2026-27` unless the user specifies another year.
7. Generate the private Excel report with `local-script/esk_otr_api.py`.
8. Send the resulting `.xlsx` file directly back to the requester as a document attachment.
9. Do not paste Aadhaar, bank account, mobile number, password, token, cookie, or other sensitive values into chat text.
10. Do not upload generated reports to GitHub.

## Known school registry

Initial known school:

- School aliases: `UMV Tetahali`, `Uchcha Madhyamik Vidyalaya Tetahali`, `Tetahali`
- Credential source: Bitwarden Secrets Manager through `eshikshakosh-run`
- Runtime aliases exposed to the child process:
  - `ESHIKSHAKOSH_USERNAME`
  - `ESHIKSHAKOSH_PASSWORD`

Do not print the values of those variables.

## Runtime location

Expected repository path:

```text
~/projects/eshikshakosh-automation
```

Expected Python runtime:

```text
~/projects/eshikshakosh-automation/.venv/bin/python
```

Expected report script:

```text
~/projects/eshikshakosh-automation/local-script/esk_otr_api.py
```

## Dependency setup

Use the repository virtual environment. Do not install Python packages into the system Python.

```bash
cd ~/projects/eshikshakosh-automation
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

## Known-school execution

For a school whose credentials are already mapped by `eshikshakosh-run`:

```bash
cd ~/projects/eshikshakosh-automation

eshikshakosh-run .venv/bin/python local-script/esk_otr_api.py \
  --udise "$ESHIKSHAKOSH_USERNAME" \
  --password "$ESHIKSHAKOSH_PASSWORD" \
  --year "2026-27"
```

Never echo the expanded command or run with shell tracing enabled.

## Unknown-school execution

For an unknown school, collect the portal user ID / UDISE and one-time password only for the current request. Pass them directly to the report process without writing them to disk, Git, memory, or logs.

Do not permanently save credentials unless the user explicitly requests credential storage and approves the separate Bitwarden write flow.

## Report delivery

After a successful run:

1. Find the newly generated `Student_OTR_Report_*.xlsx` file.
2. Build a short context message using only non-sensitive summary fields:
   - school name
   - academic year
   - total students
   - OTR registered
   - OTR pending
   - generation time
3. Attach the Excel file to the same Telegram or WhatsApp conversation.
4. If attachment upload fails, report the upload error and keep the file locally for retry.

Example context:

```text
e-ShikshaKosh Report
School: UMV Tetahali
Academic Year: 2026-27
Total Students: 220
OTR Registered: 205
OTR Pending: 15
```

The numbers above are an example format only. Always use the actual run output.

## Authorization guard

The generated workbook can contain unmasked student data, including Aadhaar, bank account, and mobile information.

Therefore:
- send an unmasked workbook only to an authorized requester in a private chat;
- if requester identity is not authorized or cannot be verified, do not generate or send the unmasked workbook;
- do not send these workbooks to groups by default.

## Failure behavior

If login, CAPTCHA, API fetch, Excel generation, or attachment upload fails:

- inspect the actual error;
- do not invent a successful result;
- do not expose secrets while debugging;
- report only the failed stage and concise technical reason;
- keep the workflow read-only.

## Final completion message

When successful, keep text concise because the Excel attachment is the primary output:

```text
Report ready.
School: <school>
Academic Year: <year>
Students: <count>
Attached: <filename>
```
