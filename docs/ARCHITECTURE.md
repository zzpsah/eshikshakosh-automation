# Architecture

## Two execution paths

### Safe manual/Colab path
```text
User supplies short-lived Bearer token
-> eshikshakosh_otr.py / Colab
-> normal TLS verification
-> masked workbook
```

### Local/VPS authorized path
```text
Telegram/WhatsApp request
-> identify authorized school/requester
-> Bitwarden-backed credential injection
-> ~/.local/bin/eshikshakosh-report
-> local-script/run_report.sh
-> .venv/bin/python local-script/esk_otr_api.py
-> portal login/token capture
-> student list + studentInfo reads
-> private .xlsx
-> REPORT_READY=<path>
-> same private channel attachment
```

## Trust boundaries
- GitHub: code and non-secret documentation only.
- Bitwarden Secrets Manager: machine/service credentials.
- VPS runtime: private credential injection and private generated reports.
- Messaging: only authorized private delivery for unmasked reports.

## Read-only boundary
The report workflow reads student data but does not submit, edit, certify, or delete portal records.

## Session logic
Academic session defaults automatically using an April-March school-year boundary. Explicit override remains available.

## Hermes routing rule
Hermes must use the verified report runner for student-report requests. It must not fall back to unrelated teacher-data extraction or ad-hoc browser selectors when the runner exists.
