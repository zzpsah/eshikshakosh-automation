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

## Scoped report examples

```bash
eshikshakosh-report --class 10
eshikshakosh-report --class 10 --section 2
eshikshakosh-report --class 11 --stream 2
eshikshakosh-report --class 12 --section 1 --stream 3
eshikshakosh-report --split-sheets
```

Optional `--mode full|masked` and `--year YYYY-YY` may be combined with these flags.
