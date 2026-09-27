# Decisions

## 2026-09-27 — Read-only portal boundary
The project may authenticate and read authorized student data but does not submit, edit, certify, or delete portal records.

## 2026-09-27 — Separate report paths
Keep the masked safe/manual flow separate from the local authorized unmasked flow.

## 2026-09-27 — Runtime credential injection
Use the verified Bitwarden launcher for known-school credentials; never print or commit values.

## 2026-09-27 — Strict Hermes route
Student-report requests use the verified local report runner and must not drift into teacher-data extraction or ad-hoc browser selectors.

## 2026-09-27 — Vibe Coding baseline
Use READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION.
