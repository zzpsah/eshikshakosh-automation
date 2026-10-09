# eShikshaKosh web deployment

## Current deployment — 9 October 2026

- GitHub source: `zzpsah/eshikshakosh-automation`, branch `main`.
- Web app source: `web/` (Next.js).
- Vercel project: `zzpsah/eshikshakosh`.
- Selected hostname: **https://eshikakoshapp.vercel.app**
- Deployment target previously reported Ready: `https://eshikshakosh-jgwtqxdxu-zzpsah.vercel.app`.
- The selected alias was assigned successfully to that deployment.
- Vercel Deployment Protection / Vercel Authentication was enabled at the last verified checkpoint; do not describe the app as anonymously/publicly accessible without checking current settings.
- The requested `eshikshakosh.vercel.app` hostname was already in use by another deployment and was not assigned.
- UDISE is a separate project/repository. Never change UDISE production or `udise-login-staging` while working here.

## Implemented

The responsive Next.js report setup UI is deployed. It offers school code, academic session, report scope and privacy messaging. It does not show student rows, portal tokens or credentials in the browser.

**The Generate Excel report action is still a placeholder.** It displays a not-connected status and does not call the portal or produce a downloadable workbook. The successful domain assignment and frontend deployment do not mean the backend is connected.

## Backend connection — pending

The existing private read-only report generator is in `local-script/esk_otr_api.py`, launched by `local-script/run_report.sh`. The private runner may produce a workbook containing sensitive student information, including Aadhaar, bank-account and mobile data. It must not be exposed as an unrestricted public process.

Before enabling report generation:

1. Add an authenticated, server-side app access gate; do not rely solely on obscurity of the URL.
2. Provide a private, authenticated route from the Vercel app to the authorized Oracle report runner. No unauthenticated public command endpoint.
3. Validate allowed school/session/scope and restrict the operation to the existing read-only report workflow.
4. Add rate limits, request validation, job timeouts, safe error messages and audit events that do not contain secrets or student data.
5. Keep portal credentials, cookies, JWTs, tokens, workbook contents and student records out of browser JavaScript and logs.
6. Deliver the workbook only through a short-lived, authenticated download route; avoid public persistent file URLs.
7. Use secure HttpOnly, SameSite cookies for any app session, with CSRF protection where applicable. Never put credentials/tokens in localStorage.
8. Verify Vercel root directory is `web` and that the project remains linked only to `zzpsah/eshikshakosh-automation`.
9. Test lint/build, unauthenticated rejection, authorized generation, download authorization/expiry, and cleanup using a controlled test—not by exposing real student data.

## Verification boundary

- Frontend source/deployment: implemented; a deployment was reported Ready and the alias assignment succeeded.
- Frontend-to-backend connection: **not implemented/verified at the last checkpoint**.
- Authenticated end-to-end Excel download: **not tested**.
- Do not claim report generation is operational until those last two items pass.

## Recovery / access

The Oracle remote-control device was reported offline at the last attempted connection on 9 October 2026. If still offline, reconnect the remote-control service before changing or testing the server. Do not work around the outage by exposing the report runner publicly.

## Required checks

Run from `web/`:

```bash
npm run lint
npm run build
```

After any changes, update this document with verified evidence and commit the docs/code together. Never commit student exports, credentials, cookies, tokens or secret environment files.
