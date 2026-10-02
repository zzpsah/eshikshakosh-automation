# Commands

## Create/use local environment
```bash
cd ~/projects/eshikshakosh-automation
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

## Verify runtime
```bash
.venv/bin/python -m playwright --version
.venv/bin/python -c "import playwright, nest_asyncio; print('runtime ok')"
```

## Generate report through installed launcher
```bash
~/.local/bin/eshikshakosh-report
```

Success requires a real workbook and a line like:
```text
REPORT_READY=<path>
```

## Update local checkout
```bash
cd ~/projects/eshikshakosh-automation
git pull --ff-only
```

## Development loop
```text
READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION
```

## Messaging slash commands

```text
/eshikshakosh
/esk
/esk-report
/eshikshakosh-report
/eshikakossh-report
```

Examples:

```text
/esk UMV Tetahali
/esk Tetahali masked
```

Default export mode is `full`. If no school is supplied, the command asks for school name. Missing Bitwarden credentials route to `/bw add` secure form.
