# Security and Privacy

- The local workbook can contain Aadhaar, bank-account, mobile, and other private student information.
- Generated reports are private operational artifacts and must not be committed to Git.
- Send unmasked reports only to an authorized requester in a private chat.
- Do not send unmasked reports to groups by default.
- Never print passwords, tokens, cookies, OTPs, secret environment variables, Aadhaar values, bank details, or mobile values in debug output.
- Hermes secret access should remain read-only through the approved Bitwarden path.
- Unknown-school credentials are one-time runtime values unless the user separately approves storage.
- Authentication success does not authorize portal mutation.
- No production deployment or consequential portal/data mutation without explicit approval.
