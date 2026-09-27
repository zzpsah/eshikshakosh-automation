# Design

## User experience
A report request should be short:

```text
request student details
-> identify school if needed
-> generate
-> return short non-sensitive summary
-> attach workbook in the same private chat
```

Do not make the user re-enter a stored authorized password for a known school.

## Failure behavior
If login, fetch, Excel generation, or attachment delivery fails:
- stop at the failed stage;
- report the concise technical reason;
- do not invent a successful file;
- do not expose secrets;
- do not fall back to unrelated portal modules.

## Output naming
Preferred future naming:
`Student_Details_<School>_<Session>.xlsx`.

Current OTR-specific naming remains until the code/runner/skill are updated together.

## Privacy
The attachment is primary output. Chat text should contain only safe summary fields such as school, session, student count, OTR registered/pending, and generation time.
