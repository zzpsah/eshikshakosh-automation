# Tasks

## Completed
- [x] Establish repo-local Python virtual environment.
- [x] Install and verify Playwright.
- [x] Add `nest_asyncio` dependency for the local workflow.
- [x] Verify Bitwarden-backed credential injection without displaying secret values.
- [x] Generate a real current-session workbook using the local runner.
- [x] Auto-derive the academic session using Apr-Mar boundaries.
- [x] Pin Hermes student-report execution to the verified local runner.
- [x] Add DevOS/Vibe Coding baseline.
- [x] Prove Telegram request -> report -> Excel attachment in the same private chat.
- [x] Prove WhatsApp request -> report -> Excel attachment in the same private chat.
- [x] Add `local-script/esk_teacher_list.py` (API list, readable labels, combined address).
- [x] Verify all teacher detail endpoints live; remove the dead `/teacher/getTeacherDetails` (HTTP 500).
- [x] Fix the Education sheet data-loss bug (`preServicedata` + `inServicedata`).
- [x] Delete the experimental `esk_teacher_unified.py`; keep API list and browser detail separate.
- [x] Move retired scripts to `student-scripts/` and `local-script/archive/`; update README paths.

## Active
- [ ] Run one real inbound WhatsApp natural-language regression after v2.5 skill synchronization; verify no redundant approval prompt and same-chat XLSX delivery.
- [ ] Verify `~/.local/bin/eshikshakosh-report` after every relevant repo/skill update.
- [ ] Rename report output to a generic `Student_Details_<School>_<Session>.xlsx` pattern.
- [ ] Update runner file matching and skill documentation after filename rename.
- [ ] Add a private school registry mapping school aliases to credential keys.
- [ ] Keep unknown-school credentials one-time unless explicit storage approval is granted.
- [ ] Finish diagnosing/hardening Hermes internal prompt/tool-trace leakage.
- [ ] Wire `esk_teacher_list.py` to a runner script if the direct-launch path proves awkward in practice.

## Guarded
- [ ] Do not introduce portal mutation without a separate explicit design and approval.
- [ ] Do not upload generated student workbooks to GitHub.


## Messaging verification

- [x] Telegram same-channel Excel delivery verified.
- [ ] WhatsApp same-channel Excel delivery verification pending.
