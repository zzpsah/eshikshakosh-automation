# e-ShikshaKosh Report Automation — Security

- Treat student records as private school data.
- Never commit exported XLSX/CSV files.
- Never commit passwords, bearer tokens, cookies, OTP/MFA material or session data.
- Safe/manual exporter masks sensitive identifiers and keeps TLS verification enabled.
- Private local automation may handle sensitive fields only inside the authorized private runtime.
- No guessed/unverified portal endpoint should be committed as an implemented feature.
- No edit/submit/delete/certify operation against portal records is implemented.
- If a sensitive artifact was historically committed, removing it from the current tree does not erase old Git history; history rewrite is a separate high-impact operation and must be planned explicitly.
