# e-ShikshaKosh Report Automation — Project

## Purpose
Maintain read-only student report extraction workflows for e-ShikshaKosh with two clearly separated runtime profiles.

## Profiles

### Safe/manual exporter
- `eshikshakosh_otr.py`
- short-lived bearer token entered only at runtime;
- normal TLS verification;
- masks sensitive identifiers in exported workbooks;
- no portal mutation.

### Private local automation
- `local-script/esk_otr_api.py`
- used only on the authorized private Oracle/local runtime;
- credentials supplied through the protected runtime secret wrapper/environment;
- generated workbooks remain local/private and are ignored by Git;
- no portal record mutation is implemented.

## Boundaries
Do not commit credentials, tokens, cookies, OTP/MFA, student exports, Aadhaar, bank-account data, mobile numbers or other private school records.
