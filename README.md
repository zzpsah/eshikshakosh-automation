# e-ShikshaKosh Automation

Private, read-only Python and Google Colab project for producing a reviewed e-ShikshaKosh student-report workbook.

## What is included

- `eshikshakosh_otr.py` — safe command-line/Colab script.
- `Eshikshakosh_OTR.ipynb` — Colab launcher for the script.
- `requirements.txt` — minimal runtime dependencies.

## Safety and data handling

This project is deliberately read-only. It does not submit, edit, certify, or delete portal records. Login is manual: enter a short-lived Bearer token only into the active runtime when prompted. Never commit tokens, cookies, passwords, OTPs, exported workbooks, Aadhaar numbers, bank-account numbers, or other student data.

The original supplied draft was not published unchanged because it disabled TLS verification, attempted to automate a CAPTCHA-like challenge, and requested unmasked Aadhaar/bank data. This maintained version uses normal TLS verification, does not automate CAPTCHA or password login, and masks sensitive data in every export.

## Run locally

```powershell
python -m pip install -r requirements.txt
python eshikshakosh_otr.py
```

The script asks for the academic year and a valid short-lived Bearer token. It writes a timestamped workbook locally. Review it before any human workflow that uses its contents.

## Run in Google Colab

Open `Eshikshakosh_OTR.ipynb`, upload `eshikshakosh_otr.py` when prompted, then run the final cell. The token stays in that Colab runtime only.

## Verification status

- Source structure: checked locally.
- Notebook JSON: checked locally.
- Live e-ShikshaKosh authentication and API response shape: not tested in this repository.
- Portal mutation: none implemented or attempted.

## Local Hermes/VPS workflow

The VPS integration now uses a separate local automation path under `local-script/`. This path is intentionally distinct from the safer masked Colab/manual-token workflow described above.

Key local components:

- `local-script/esk_otr_api.py` — read-only Playwright/API report generator that can include unmasked student details.
- `local-script/run_report.sh` — validated local runner that uses the repo virtual environment and emits `REPORT_READY=<path>` on success.
- `local-script/install-hermes-skill.sh` — installs the Hermes skill and `~/.local/bin/eshikshakosh-report` wrapper.
- `skills/eshikshakosh-otr/SKILL.md` — same-channel Telegram/WhatsApp workflow and strict execution route.
- `requirements.txt` — includes the local Playwright and `nest-asyncio` runtime dependencies.

The local report path is read-only with respect to portal data, but its workbook can contain unmasked Aadhaar, bank-account, mobile, and related student information. Generated workbooks are private operational artifacts and must not be committed to GitHub.

### Verified VPS checkpoint

A real local run succeeded for UMV Tetahali for the current academic session. The verified summary was:

- Total students: 220
- OTR registered: 2
- OTR pending: 218
- Aadhaar values present: 219
- Bank accounts present: 220
- Mother names present: 220

The current academic session is derived automatically using an April-March boundary unless explicitly overridden.

### Report filename

The local Hermes/VPS report now uses:

```text
Student_Details_<School>_<Session>.xlsx
```

The school name is sanitized for filesystem safety.

### Hermes execution rule

For e-ShikshaKosh student-report requests, Hermes must use the verified local command path and must not improvise with generic browser scraping or switch to teacher-data extraction.

Expected route:

```text
request -> identify school -> resolve authorized credentials
        -> ~/.local/bin/eshikshakosh-report
        -> REPORT_READY=<path>
        -> send the .xlsx back in the same private channel
```

Telegram end-to-end attachment delivery is verified. WhatsApp end-to-end attachment delivery is still pending verification.

### Known Hermes issue

A messaging-session defect was observed where internal attachment/tool-routing text leaked into user-visible responses. Request-dump inspection showed those phrases originated from normal internal instructions/tool descriptions; the problem is their accidental echo in the outward reply. A fresh-session reset removed the obvious leak in one immediate test, but the issue remains open until repeated channel tests pass.



## DevOS / Vibe Coding project context

Read these before substantial changes:

- [PRD](PRD.md)
- [Development rules](RULES.md)
- [Tasks](TASKS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Design](docs/DESIGN.md)
- [Test plan](docs/TEST_PLAN.md)
- [Security](docs/SECURITY.md)
- [Decisions](docs/DECISIONS.md)
- [Project memory](docs/MEMORY.md)
- [Commands](docs/COMMANDS.md)
- [History](docs/HISTORY.md)

Material work follows:

```text
READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION
```
