# Current State

Last documented: 2026-10-17

## Teacher export — 2026-10-17

Two deliberately separate methods, both read-only:

| Script | Method | Output |
|---|---|---|
| `modules/teacher/scripts/esk_teacher_list.py` | API (list + per-teacher `registrationInfo`) | 28-column roster, readable labels, combined address |
| `modules/teacher/scripts/esk_teacher_detail_extract.py` | Browser / Playwright | 7-sheet full profile |

Verified live against UMV Tetahali (16 teachers):

- All seven detail endpoints return HTTP 200. `/teacher/getTeacherDetails` returns HTTP 500
  `Server Error` for every key tried and was **removed** from the extractor.
- The list endpoint returns raw numeric codes but unmasked mobile/PAN/Aadhaar;
  `/teacher/registrationInfo` returns readable labels but masked identifiers. The list export
  merges both.
- **Education data was being silently dropped**: the endpoint returns `preServicedata` +
  `inServicedata`, which `_rows()` never looked for. Fixed — the Education sheet went from
  `No records for this school` to 18 rows on the same school.
- `gpfNo` / `uanNo` are genuinely absent in the portal for these schools.
- `esk_teacher_unified.py` deleted at the user's direction; the two methods stay separate.

## Verified local workflow
- Repo-local `.venv` is used.
- Playwright and `nest_asyncio` are installed for the local path.
- Bitwarden-backed credential injection was verified without intentionally displaying secret values.
- Student OTR report generation verified. Verified summary from that run: 220 students; 2 OTR registered; 218 pending; 219 Aadhaar values present; 220 bank accounts; 220 mother names.
- Academic session defaults automatically using an April-March boundary.
- Hermes student-report execution is pinned to `~/.local/bin/eshikshakosh-report`.
- Telegram and WhatsApp same-private-chat Excel attachment delivery are verified.
- Student OTR code now lives in `modules/student/scripts/esk_otr_api.py`. `modules/student/run_report.sh`
  stays a live runner and was repointed at that new path; `install-hermes-skill.sh` is retired
  under `modules/teacher/archive/`.
- **Student report path verified working after the move** — a live run through
  `~/.local/bin/eshikshakosh-report` produced a fresh `Student_Details_..._All.xlsx`.

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

## Remote access handoff
- Canonical access instructions: `docs/REMOTE-ACCESS.md`.
- New AI chats must discover the current Desktop Commander device with `list_devices`, choose the online `oracle-server`, and verify it with `ping` before touching live runtime state.
- GitHub access alone does not provide Oracle VPS control.