# e-ShikshaKosh Report Automation — Tests

Last verified: 2026-10-02.

Passed:
- `bash -n local-script/install-hermes-skill.sh`;
- `bash -n local-script/run_report.sh`;
- `python3 -m py_compile eshikshakosh_otr.py local-script/esk_otr_api.py`;
- `.venv/bin/python local-script/esk_otr_api.py --help`;
- `git diff --check`.

Not performed during this reconciliation:
- no live portal login;
- no CAPTCHA/OTP interaction;
- no student-data export;
- no portal mutation.
