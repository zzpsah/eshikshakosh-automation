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
