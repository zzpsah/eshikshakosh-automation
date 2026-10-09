# eShikshaKosh web deployment

## Target
- Vercel project: `eshikshakosh`
- Requested hostname: `https://eshikshakosh.vercel.app` (availability must be confirmed by Vercel)
- Source: `web/` in this repository
- UDISE project/deployments are separate and must not be modified.

## Current web implementation
A Next.js UI exists in `web/`. It provides a report setup screen and does not render student rows, portal tokens, or credentials in the browser. The Generate action is deliberately a safe stub until the protected backend is implemented and configured; it does not send portal requests yet.

## Required before production
1. Configure a private access gate and server-side session protection.
2. Establish a secure authenticated path from the Vercel server to the Oracle report runner. Do not expose a public unauthenticated report endpoint.
3. The server-side bridge must invoke only the existing read-only runner, validate permitted school/session/scope, apply rate limits, and return a short-lived authenticated download for the generated workbook.
4. Never pass portal credentials, JWTs, cookies, student records, or workbook contents to client-side JavaScript or logs.
5. Do not use localStorage for credentials or tokens. Use secure, HttpOnly, SameSite cookies for app sessions and CSRF protection for state-changing requests.
6. Configure Vercel project root directory as `web`; set the project name to `eshikshakosh`. Do not link this repo to any UDISE Vercel project.
7. Confirm the requested `eshikshakosh.vercel.app` hostname is available and assigned to this project before reporting the URL as live.

## Verification
Run `npm run lint` and `npm run build` from `web/`. Deployment must remain disabled until the private backend/access gate is in place and tested end-to-end.
