# Project Memory

## Verified state
- Local repo expected at `~/projects/eshikshakosh-automation`.
- Project uses a repo-local `.venv`.
- Playwright and `nest_asyncio` are installed for the local flow.
- Bitwarden-backed credential injection has been verified without intentionally displaying secret values.
- Student OTR code lives in `modules/student/scripts/esk_otr_api.py`; it produced a real current-session workbook.
- Verified run summary: 220 students; 2 OTR registered; 218 pending; 219 Aadhaar values present; 220 bank accounts; 220 mother names.
- Session defaults automatically using Apr-Mar boundaries.
- Hermes skill is pinned to the verified local runner.
- Telegram and WhatsApp same-private-chat Excel delivery are verified.
- A messaging internal-trace echo issue was observed; a fresh session reset removed the obvious raw dump once, but the issue is not considered closed.

## Teacher export — 2026-10-17
- `modules/teacher/scripts/esk_teacher_list.py` — API-based 28-column roster; merges readable labels from
  `/teacher/registrationInfo` with unmasked mobile/PAN/Aadhaar from the list endpoint, and
  builds a single-cell combined address. Verified: 16 teachers at UMV Tetahali.
- `modules/teacher/scripts/esk_teacher_detail_extract.py` — browser-based 7-sheet profile. Verified:
  16 teachers, 6 sections each.
- The API list path and the browser detail path stay **separate** by explicit user directive.
- `/teacher/getTeacherDetails` is dead (HTTP 500 for every key) and was removed.
- Education data was being silently dropped (`preServicedata` + `inServicedata` were never
  read); fixed — 2 rows to 18 rows on the same school.
- `gpfNo` / `uanNo` are genuinely absent in the portal; write a blank cell, not `None`.
- `esk_teacher_unified.py` was deleted; do not recreate it.

## Next
- Rename output to Student Details naming.
- Add a private multi-school credential registry.
- Continue hardening Hermes messaging output.
- Wire `esk_teacher_list.py` to a runner if direct launch proves awkward.

## Memory rule
Never store credentials, secret values, tokens, cookies, OTPs, or private student records here.


## Report naming and messaging

- Report filename pattern: `Student_Details_<School>_<Session>.xlsx` with a filesystem-safe school component.
- Telegram same-private-chat Excel delivery is verified.
- WhatsApp same-private-chat Excel delivery verified on 2026-10-03 using a real masked Class 10 report.


## Messaging intent behavior
- As of v2.5.0, normal Hindi/Hinglish report requests should route without requiring slash commands.
- Do not ask `continue/proceed/confirm` after a clear authorized read-only report request.
- Ask only for genuinely missing school/scope/authorization facts.
- Keep both installed skill aliases synchronized until the legacy alias is deliberately retired.