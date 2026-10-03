# Current State

Last documented: 2026-09-27

## Verified local workflow
- Repo-local `.venv` is used.
- Playwright and `nest_asyncio` are installed for the local path.
- Bitwarden-backed credential injection was verified without intentionally displaying secret values.
- `local-script/esk_otr_api.py` generated a real current-session workbook.
- Verified summary from that run: 220 students; 2 OTR registered; 218 pending; 219 Aadhaar values present; 220 bank accounts; 220 mother names.
- Academic session defaults automatically using an April-March boundary.
- Hermes student-report execution is pinned to `~/.local/bin/eshikshakosh-report`.
- Telegram and WhatsApp same-private-chat Excel attachment delivery are verified.

## Known issue
Hermes messaging exposed internal prompt/tool-routing text in a user-visible reply. Request-dump inspection showed the strings existed in normal internal instructions/tool metadata. A fresh-session reset removed the obvious raw dump once, but the issue is not considered closed.

## Next
- Keep scoped report behavior regression-tested after portal/API changes.
- Add additional schools only through the secure credential mapping flow.
- Continue Hermes output hardening.

## Messaging report command — 2026-10-02

- `/eshikshakosh` plus short/typo aliases are supported.
- School name is requested when absent.
- Known aliases can resolve Bitwarden credentials automatically.
- Missing credentials use secure `/bw add` flow.
- Export mode is user-controlled, default `full`.

## Scoped report update — 2026-10-03

Class/section/stream filters and split-sheet output are implemented in the private VPS report path. Messaging skill v2.4.0 documents natural-language scope selection. Verified proof: a real filtered Class 10 masked run and WhatsApp same-private-chat attachment delivery both passed.


## Natural-language messaging update — 2026-10-03

- Skill behavior advanced to v2.5.0.
- Both active Hermes skill names, `eshikshakosh-otr` and legacy `eshikshakosh-report`, are synchronized to the same rules to avoid inconsistent routing.
- Ordinary Hindi/Hinglish WhatsApp/Telegram requests are accepted without requiring a slash command.
- A clear read-only report request is treated as authorization to generate and return the XLSX in the same authorized private chat; no repeated `continue/proceed/confirm` prompt is required.
- Follow-up questions are limited to genuinely missing school/scope/authorization information.
- Local Hermes parser test passed for Class 10, Class 11 Science, and all-class split-sheet phrasing.
- Real inbound WhatsApp natural-language regression test remains pending.
