# Development Rules

1. Follow: READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION.
2. Preserve the project as read-only with respect to e-ShikshaKosh portal records.
3. Use the repository virtual environment; do not install project packages into Ubuntu system Python.
4. For known-school VPS execution, use the verified local runner and Bitwarden injection path.
5. Do not improvise with generic browser scraping when `~/.local/bin/eshikshakosh-report` exists.
6. Do not switch a student-report request into teacher-data extraction.
7. Browser navigation or login redirect alone is not report success; require a real generated workbook.
8. Never print passwords, tokens, cookies, Aadhaar values, bank details, mobile numbers, or secret environment variables in logs/chat.
9. Unmasked workbooks are private operational artifacts; never commit them to GitHub.
10. Do not send unmasked workbooks to groups or unverified requesters.
11. Unknown-school credentials are one-time runtime values unless explicit storage approval is given.
12. Keep session/year automatic by default; only override when requested.
13. Record verified run behavior and unresolved delivery/tooling issues in durable docs.
