# e-ShikshaKosh Report Automation — Architecture

```text
Safe/manual path
user token -> eshikshakosh_otr.py -> read-only API -> masked local workbook

Private local path
Hermes/private command
      |
      v
protected secret wrapper/environment
      |
      v
local-script/run_report.sh
      |
      v
local-script/esk_otr_api.py
      |
      v
read-only portal/API workflow -> private local workbook
```

The generated workbook is an output artifact, not source code, and must remain outside Git.
