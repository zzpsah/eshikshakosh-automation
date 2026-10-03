# Project Memory

## Verified state
- Local repo expected at `~/projects/eshikshakosh-automation`.
- Project uses a repo-local `.venv`.
- Playwright and `nest_asyncio` are installed for the local flow.
- Bitwarden-backed credential injection has been verified without intentionally displaying secret values.
- `local-script/esk_otr_api.py` produced a real current-session workbook.
- Verified run summary: 220 students; 2 OTR registered; 218 pending; 219 Aadhaar values present; 220 bank accounts; 220 mother names.
- Session defaults automatically using Apr-Mar boundaries.
- Hermes skill is pinned to the verified local runner.
- Telegram and WhatsApp same-private-chat Excel delivery are verified.
- A messaging internal-trace echo issue was observed; a fresh session reset removed the obvious raw dump once, but the issue is not considered closed.

## Next
- Prove same-channel file delivery.
- Rename output to Student Details naming.
- Add a private multi-school credential registry.
- Continue hardening Hermes messaging output.

## Memory rule
Never store credentials, secret values, tokens, cookies, OTPs, or private student records here.


## Report naming and messaging

- Report filename pattern: `Student_Details_<School>_<Session>.xlsx` with a filesystem-safe school component.
- Telegram same-private-chat Excel delivery is verified.
- WhatsApp same-private-chat Excel delivery verified on 2026-10-03 using a real masked Class 10 report.
