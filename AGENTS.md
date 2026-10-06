# Project AI Entry Point

This repository is managed by ChatGPT Development OS (DevOS).

Before substantial work:

1. Read `DEVOS.md`.
2. Read `PRD.md`, `RULES.md`, and `TASKS.md`.
3. Read `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/TEST_PLAN.md`, `docs/SECURITY.md`, `docs/DECISIONS.md`, and `docs/MEMORY.md`.
4. Read `.ai/PROJECT.md`, `.ai/CURRENT-STATE.md`, `.ai/ARCHITECTURE.md`, `.ai/DECISIONS.md`, and `.ai/TASKS.md`.
5. Inspect current source, runner scripts, skill, and Git history before changing behavior.
6. For student-report requests, preserve the verified local-runner path.

## DevOS Vibe Coding baseline

```text
READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION
```

## Safety

- Portal behavior remains read-only.
- Unmasked workbooks are private runtime artifacts.
- Do not expose passwords, tokens, cookies, Aadhaar, bank, mobile, or secret environment values in logs/chat.
- Do not send unmasked reports to unauthorized users or groups.
- Do not replace the verified local runner with ad-hoc browser/teacher-data scraping.
- No production deployment or consequential portal/data mutation without explicit user approval.

## Remote access / Desktop Commander

For authorized Oracle VPS access, read [`docs/REMOTE-ACCESS.md`](docs/REMOTE-ACCESS.md). A new AI chat must use Desktop Commander `list_devices`, select the online `oracle-server`, ping it, and only then operate on the live server. Do not confuse GitHub access with VPS/runtime access.
