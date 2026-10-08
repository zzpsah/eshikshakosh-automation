# eShikshaKosh Live OTR Fetch Fix — 2026-10-08

## Incident
The live OTR fetch reached eShikshaKosh login successfully but failed at `student/viewStudentList` with HTTP 401 (`Bad token; invalid JSON`). A previous request-shape regression also caused empty rosters when extra district/block/cluster filters were sent.

## Root causes
1. The login response contains both a short `access_token` and a JWT in the `token` field. Recursive token discovery iterated `access_token` first and incorrectly stored the short token as the primary API token.
2. The roster request had been expanded with district/block/cluster/schoolEncId fields. The proven school-scoped request uses `searchSchoolId` and `academicYear`, plus optional class/stream/section filters.
3. The live working tree had the school-scope fallback change from commit `12cca8b` missing from the active file, so school ID resolution was restored to `_find_school_id(...)`.

## Fix
- Prefer the response `token` field as the primary JWT.
- Keep `access_token` separate for the secondary header.
- Restore `_find_school_id(...)` for JWT/profile/UDISE fallback.
- Restore the proven school-scoped roster payload.
- Keep optional class/stream/section filters conditional.

## Validation
- Python compilation passed.
- Live Bitwarden-backed eShikshaKosh login returned HTTP 200.
- JWT token was confirmed to decode successfully (non-secret metadata only).
- Full live OTR export completed successfully for academic year `2026-27`.
- Output workbook: 220 student records, 221 rows including header, 27 columns, single roster sheet.
- No credentials or token values are stored in this document.

## Security note
The live test used the server-side Bitwarden Secrets Manager read-only identity. Secret values were not intentionally persisted to the repository, logs, or documentation.
