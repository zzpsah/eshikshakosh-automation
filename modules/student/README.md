# Student module

Canonical VPS directory: `~/projects/eshikshakosh-automation/modules/student/`.

- `run_report.sh`: private student report runner, invoked by `~/.local/bin/eshikshakosh-report`.
- `scripts/esk_otr_api.py`: Playwright/API report generator for the private VPS workflow.
- `scripts/eshikshakosh_otr.py`: manual short-lived bearer-token CLI/Colab script.
- `notebooks/Eshikshakosh_OTR.ipynb`: preserved notebook launcher.
- `notebooks/Eshikshakosh_OTR_ORIGINAL.ipynb`: preserved original/reference notebook.
- `READ_ME_FIRST.txt`: older local workflow notes; Windows paths in it are historical.

## Actual Oracle VPS paths

| Purpose | Path |
|---|---|
| Repository | `/home/prashant/projects/eshikshakosh-automation` |
| Runner | `modules/student/run_report.sh` |
| API script | `modules/student/scripts/esk_otr_api.py` |
| Launcher | `/home/prashant/.local/bin/eshikshakosh-report` |
| Secret wrapper | `/home/prashant/.local/bin/eshikshakosh-run` |
| Python | `/home/prashant/projects/eshikshakosh-automation/.venv/bin/python` |
| Generated student workbook | `/home/prashant/exports/student/`; historical workbooks in `archive/` |

Supported example: `~/.local/bin/eshikshakosh-report --class 10 --mode masked`. Do not put secrets or exported student data in this module or Git.

For Google Colab, the preserved notebook asks you to upload `eshikshakosh_otr.py`; upload the file from `modules/student/scripts/` and keep the repository `requirements.txt` available. The notebook itself was intentionally preserved unchanged.
