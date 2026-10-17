# School Data Desk — e-ShikshaKosh workflow portal

This is the Next.js frontend deployed as the Vercel project `eshikshakosh`.

## Current purpose

The website is a **workflow guide / command builder**, not a connected report-generation
service. It lists the supported student and teacher report workflows and lets an operator
copy the appropriate command for execution on the authorised Oracle VPS.

- Student details: `~/.local/bin/eshikshakosh-report`
- Teacher roster: `modules/teacher/run_teacher_report.sh --school Sahaspur`
- Full teacher profile: `modules/teacher/run_teacher_detail_report.sh --school Sahaspur`

Teacher commands use the existing school registry and protected credential wrapper. Run
teacher commands from the `eshikshakosh-automation` repository root on the VPS.

## Design

The page is an **Operate** surface, not a landing page. There is deliberately no hero, no
decorative illustration and no equal-weight feature-card grid — the operator's job is to
pick a workflow, set the school and copy a command, so density and a clear selection state
carry the layout.

| Element | Choice |
|---|---|
| Type | IBM Plex Sans + IBM Plex Mono via `next/font` (self-hosted, no render-blocking import) |
| Palette | Neutral paper + one green accent; no gradient, no decorative art |
| Workbench | Two panes — workflow list with a filled selected state, and an action pane |
| Reference | A dense table of every workflow, entry point, output and scope |
| Motion | 120ms transitions, disabled under `prefers-reduced-motion` |
| Accessibility | `:focus-visible` rings, `aria-pressed` / `aria-current`, `aria-live` copy feedback, 42px touch targets |

## Important integration boundary

The current Next.js app has no API route or authenticated connection to the Oracle VPS
runner. Do not claim that clicking a button generates or downloads a report. This frontend
intentionally makes the limitation visible and does not ask for portal passwords, student
data, teacher data, or tokens.

To enable in-browser generation in a future change, implement a narrowly scoped
authenticated server-side job API with access control, school-scope validation, safe job
status polling, and private file delivery. Do not expose VPS credentials or invoke shell
commands directly from a browser. Keep the existing report scripts as the source of truth.

## Local development and verification

```bash
npm ci
npm run lint
npm run build
npm run dev
```

The UI is responsive and supports keyboard-accessible workflow selection. It does not
display personal records. Generated Excel files remain on the existing report workflow and
must not be committed to this repository.

## Vercel

The Vercel project is `eshikshakosh`; its root directory is configured as `web`. The
verified production alias is `https://eshikshakosh-coral.vercel.app`, which is publicly
reachable (no login wall) and carries `noindex, nofollow`. Keep `.vercel/project.json`
local and out of Git.
