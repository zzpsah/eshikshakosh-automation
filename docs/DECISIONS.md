# Decisions

## 2026-09-27 — Keep portal workflow read-only
Student report automation may authenticate and read authorized data, but does not edit, certify, delete, or submit portal records.

## 2026-09-27 — Separate safe and private report paths
Keep the safer masked manual/Colab flow separate from the local authorized unmasked VPS flow.

## 2026-09-27 — Runtime secret injection
Known-school credentials are injected through the verified Bitwarden launcher and must not be printed or committed.

## 2026-09-27 — Automatic current session
Default academic session is computed using the April-March boundary; explicit override is optional.

## 2026-09-27 — Strict Hermes route
Student-report requests must use `~/.local/bin/eshikshakosh-report`; no generic browser/teacher-data fallback when the runner exists.

## 2026-09-27 — Same-channel delivery
Telegram requests should return Telegram attachments; WhatsApp requests should return WhatsApp attachments, subject to authorization and actual channel file-send capability.

## 2026-09-27 — Vibe Coding baseline
All substantial work follows READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION.
