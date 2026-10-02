# e-ShikshaKosh Report Automation — Handoff

## Resume here
1. Read PROJECT.md, CURRENT_STATE.md, SECURITY.md and TESTS.md.
2. Run `git status --short` before any change.
3. Keep generated workbooks outside Git.
4. Treat `eshikshakosh_otr.py` as the safe/manual exporter.
5. Treat `local-script/esk_otr_api.py` as private-runtime code.
6. Do not implement teacher endpoints from guesses; observe real network/API behavior first.
7. Verify read-only behavior before any portal automation extension.

## Safe checks
```bash
bash -n local-script/install-hermes-skill.sh
bash -n local-script/run_report.sh
python3 -m py_compile eshikshakosh_otr.py local-script/esk_otr_api.py
.venv/bin/python local-script/esk_otr_api.py --help
git diff --check
```
