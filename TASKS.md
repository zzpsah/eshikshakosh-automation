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

## Active
- [ ] Verify `~/.local/bin/eshikshakosh-report` after every relevant repo/skill update.
- [ ] Prove Telegram request -> report -> Excel attachment in the same private chat.
- [ ] Prove WhatsApp request -> report -> Excel attachment in the same private chat.
- [ ] Rename report output to a generic `Student_Details_<School>_<Session>.xlsx` pattern.
- [ ] Update runner file matching and skill documentation after filename rename.
- [ ] Add a private school registry mapping school aliases to credential keys.
- [ ] Keep unknown-school credentials one-time unless explicit storage approval is granted.
- [ ] Finish diagnosing/hardening Hermes internal prompt/tool-trace leakage.

## Guarded
- [ ] Do not introduce portal mutation without a separate explicit design and approval.
- [ ] Do not upload generated student workbooks to GitHub.
