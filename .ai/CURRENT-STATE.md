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
- Same-channel Telegram/WhatsApp attachment delivery still needs end-to-end verification.

## Known issue
Hermes messaging exposed internal prompt/tool-routing text in a user-visible reply. Request-dump inspection showed the strings existed in normal internal instructions/tool metadata. A fresh-session reset removed the obvious raw dump once, but the issue is not considered closed.

## Next
- Prove Telegram file delivery.
- Prove WhatsApp file delivery.
- Rename output to Student Details naming.
- Add private multi-school credential mapping.
- Continue Hermes output hardening.

## Messaging report command — 2026-10-02

- `/eshikshakosh` plus short/typo aliases are supported.
- School name is requested when absent.
- Known aliases can resolve Bitwarden credentials automatically.
- Missing credentials use secure `/bw add` flow.
- Export mode is user-controlled, default `full`.

## Scoped report update — 2026-10-03

Class/section/stream filters and split-sheet output are implemented in the private VPS report path. Messaging skill v2.4.0 documents natural-language scope selection. Remaining proof: one real filtered run and WhatsApp same-private-chat attachment delivery.
