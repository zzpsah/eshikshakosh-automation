# Architecture

Two supported paths:

```text
Safe manual/Colab:
short-lived Bearer token -> maintained safe script -> masked workbook

Local/VPS:
authorized request -> school resolution -> Bitwarden runtime injection
-> ~/.local/bin/eshikshakosh-report
-> local-script/run_report.sh
-> .venv/bin/python local-script/esk_otr_api.py
-> read-only portal/API fetch
-> private .xlsx
-> REPORT_READY=<path>
-> same private messaging channel
```

GitHub stores code/non-secret docs only. Generated unmasked reports remain private runtime artifacts.
