# e-ShikshaKosh Report Automation — Tests

Last verified: 2026-10-02.

Passed:
- `bash -n modules/teacher/archive/install-hermes-skill.sh`;
- `bash -n modules/student/run_report.sh`;
- `python3 -m py_compile eshikshakosh_otr.py modules/student/scripts/esk_otr_api.py`;
- `.venv/bin/python modules/student/scripts/esk_otr_api.py --help`;
- `git diff --check`.

Not performed during this reconciliation:
- no live portal login;
- no CAPTCHA/OTP interaction;
- no student-data export;
- no portal mutation.

## Scoped report static verification — 2026-10-03

- `bash -n` passes for install, runner and Bitwarden wrapper scripts.
- Python compilation passes for root and private report scripts.
- Private report `--help` exposes class/section/stream/split-sheet options.
- Generated workbooks remain ignored by Git.

## Real scoped + WhatsApp verification — 2026-10-03

- `eshikshakosh-report --class 10 --mode masked`: PASS.
- Current-session Class 10 API filter: 34 students.
- Workbook masking check: Aadhaar 34/34 masked; bank account 34/34 masked; mobile 34/34 masked.
- Same-private-chat WhatsApp document send: PASS.
- Oracle plugin handler maps Class 12 Section 1 Commerce masked to the expected launcher flags: PASS.