# Test Plan

## Environment
- Use repository `.venv`.
- Verify Playwright import/version.
- Verify `nest_asyncio` import.
- Never use `--break-system-packages`.

## Credential path
- Verify launcher syntax.
- Verify expected runtime aliases exist inside the child process.
- Verify secret values are not printed.
- Verify original structured secret variable names are removed where intended.

## Report generation
- Run `~/.local/bin/eshikshakosh-report`.
- Require a real generated `.xlsx`.
- Require `REPORT_READY=<path>` from the wrapper.
- Check summary counts against actual run output.
- Verify current-session default around Apr-Mar boundary.

## Hermes routing
- Student report request must invoke the verified local runner.
- It must not switch to teacher-data extraction.
- It must not improvise generic browser selectors.

## Messaging delivery
Test separately:
1. Telegram private request -> generated file -> Telegram attachment.
2. WhatsApp private request -> generated file -> WhatsApp attachment.
3. Unauthorized/group request -> unmasked report blocked.

## Regression
- Generated workbooks remain Git-ignored/private.
- No portal mutation is introduced.
- No secrets or sensitive values appear in logs/chat.
