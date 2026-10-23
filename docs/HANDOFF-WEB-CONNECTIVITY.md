# Handoff — Web Workbench ↔ VPS Gateway Connectivity

**Status:** working in production as of 2026-10-23.
**Audience:** the next AI agent (or human) taking this project forward.
**Read this first:** this document is the source of truth for how the browser app
reaches the VPS. The older docs (`ARCHITECTURE.md`, `WEB-DEPLOYMENT.md`,
`REMOTE-ACCESS.md`, `web/README.md`) are **stale** — they describe a state where the
backend was "not yet implemented". Trust this file, then verify live state.

---

## 1. What this system is

A Next.js web app (deployed on Vercel, public URL, no login wall) lets a user pick a
report workflow and generate an Excel workbook. The app itself does **no** data
extraction and holds **no** credentials. It talks to a private gateway on the Oracle VPS,
which is the only component that knows the job-service bearer token and the workbook bytes.

```
browser ──HTTPS──▶ Vercel Next.js ──HTTPS + token──▶ Tailscale Funnel ──▶ gateway (VPS)
                                                                       │
                                                          Bearer token│
                                                                       ▼
                                                              job service (VPS)
                                                                       │
                                                          subprocess  ▼
                                                       read-only report runners
                                                                       │
                                                                       ▼
                                                              ~/exports/*.xlsx
```

**Invariant to preserve:** portal credentials, the job-service bearer token, and
workbook bytes never leave the VPS. The browser only ever holds a job id and a
short-lived signed download link.

---

## 2. Component map

| # | Component | File | Listen | Managed by |
|---|---|---|---|---|
| 1 | Report gateway | `shared/gateway/server.py` | `127.0.0.1:8790` | `esk-gateway.service` |
| 2 | Job service | `shared/jobserver/server.py` | `127.0.0.1:8787` | **not a service — see §8** |
| 3 | Web app (Next.js) | `web/` | `127.0.0.1:3011` | `esk-web.service` (local) + Vercel (prod) |
| 4 | Student runner | `~/.local/bin/eshikshakosh-report` | — | invoked by job service |
| 5 | Teacher runner | `modules/teacher/run_teacher_report.sh`, `run_teacher_detail_report.sh` | — | invoked by job service |

### 2.1 Gateway (`shared/gateway/server.py`)

Python **stdlib only** (no `requirements.txt` changes). Invoked from the repo venv:

```bash
.venv/bin/python shared/gateway/server.py --host 127.0.0.1 --port 8790
```

Routes:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/healthz` | none | public liveness — the only unauthenticated route |
| GET | `/v1/config` | `x-report-token` | capabilities: schools, workflows, classes, modes |
| POST | `/v1/reports` | `x-report-token` | start a job; body `{workflow, school?, class?, mode?, session?}` |
| GET | `/v1/reports/<id>` | `x-report-token` | status + file name/size — **never a filesystem path** |
| GET | `/dl/<signed-token>` | `x-report-token` | single-use, TTL-bounded workbook bytes |

Config file `shared/gateway/config.json` (mode `0600`, operator-owned, **never commit**):

```json
{
  "app_token":   "<64-char secret — the x-report-token the app sends>",
  "job_token":   "<bearer token forwarded to the job service>",
  "job_url":     "http://127.0.0.1:8787",
  "download_ttl": 600,
  "retention_hours": 24,
  "max_jobs": 200,
  "allow_public": false
}
```

- `app_token` is generated once with `python shared/gateway/server.py --init`.
- Download links are HMAC-signed, single-use, TTL = `download_ttl` seconds.
- Finished jobs and their workbooks are purged after `retention_hours`.
- Binding a public address is **refused** unless `allow_public` is set, because that
  would require publishing the node's tailnet key and would expose student data.

### 2.2 Job service (`shared/jobserver/server.py`)

Python stdlib only. Invoked via `shared/jobserver/run.sh`:

```bash
JOB_SERVER_TOKEN=<secret> bash shared/jobserver/run.sh
```

Routes:

| Method | Path | Auth |
|---|---|---|
| GET | `/health` | none |
| POST | `/jobs` | `Authorization: Bearer <JOB_SERVER_TOKEN>` |
| GET | `/jobs/<id>` | same |
| GET | `/jobs/<id>/download` | same |

**Input allowlists** (server-side, not client-side):

```
workflows = {student, roster, detail}
schools   = {Sahaspur, Tetahali}
classes   = {"", 9, 10, 11, 12}
modes     = {full, masked}
session   = ^\d{4}-\d{2}$
```

**Runner dispatch** (`build_command`):

| workflow | command |
|---|---|
| `student` | `~/.local/bin/eshikshakosh-report [--class N] [--mode M] [--year YYYY-YY]` |
| `roster` | `bash modules/teacher/run_teacher_report.sh --school <S>` |
| `detail` | `bash modules/teacher/run_teacher_detail_report.sh --school <S>` |

**Output detection:** the student runner emits a `REPORT_READY=<path>` line on stdout;
the teacher runners produce a new file under `~/exports`, detected by diffing the
exports directory before/after the subprocess.

**Other properties:** subprocess timeout 900 s, single-run lock (runs are serialized),
per-IP rate limit 20 req/60 s, audit log records actions/outcomes only.

**State files:**

| Path | Content |
|---|---|
| `~/.local/share/jobserver/jobs.json` | job records |
| `~/.local/share/jobserver/audit.log` | append-only audit trail |

### 2.3 Web app (`web/`)

Vercel project `eshikshakosh`, root directory `web`, production alias
`https://eshikshakosh-coral.vercel.app` (public, `noindex, nofollow`).
`.vercel/project.json` holds `projectId prj_Bskn8kS7tFN4X0hrKggiNarP8spC` — keep local, out of Git.

API routes — all four are thin proxies to the gateway:

| Next.js route | Gateway call |
|---|---|
| `GET /api/config` | `GET ${ESK_GATEWAY_URL}/v1/config` |
| `POST /api/reports` | `POST ${ESK_GATEWAY_URL}/v1/reports` |
| `GET /api/reports/[id]` | `GET ${ESK_GATEWAY_URL}/v1/reports/<id>` |
| `GET /api/reports/[id]/download` | `GET ${ESK_GATEWAY_URL}/v1/reports/<id>` then `GET ${ESK_GATEWAY_URL}/dl/<signed>` |

Every proxy sends `x-report-token: ${ESK_GATEWAY_TOKEN}`. Unconfigured env → HTTP 503;
gateway unreachable → HTTP 502.

**The download route matters:** the signed link is single-use and short-lived, so the
route mints and redeems it **server-side**, then streams the bytes. The browser only
ever sees the job id — never the signed token, never a server path.

Env vars (`.env.example` is committed; `.env.local` and Vercel project env hold values):

```
ESK_GATEWAY_URL=https://oracle-server.tail2b7fe2.ts.net/gw
ESK_GATEWAY_TOKEN=<same value as gateway app_token>
```

---

## 3. End-to-end request path (the actual communication path)

### 3.1 Page load / capability fetch

```
1. browser            GET  https://eshikshakosh-coral.vercel.app/api/config
2. Vercel route       GET  https://oracle-server.tail2b7fe2.ts.net/gw/v1/config
                          header: x-report-token: <app_token>
3. Tailscale Funnel   443 handler /gw  →  proxy http://127.0.0.1:8790   (prefix /gw stripped)
4. gateway            verifies x-report-token against config.json app_token
5. gateway            returns {schools, workflows, classes, modes}
6. Vercel             passes JSON through to the browser
```

### 3.2 Start a report

```
1. browser            POST /api/config … no — POST /api/reports {workflow, school}
2. Vercel             POST <gw>/v1/reports  header x-report-token
3. gateway            validates body, allocates job id, forwards to job service:
                        POST http://127.0.0.1:8787/jobs
                        header Authorization: Bearer <job_token>
4. job service        validates against allowlists, spawns runner thread, returns {id, status}
5. job service        runs subprocess (student runner / teacher runner), writes ~/exports/*.xlsx
6. gateway            returns {id, status:"queued"} to Vercel → browser
```

### 3.3 Poll status

```
browser  GET /api/reports/<id>  →  Vercel  →  <gw>/v1/reports/<id>
                                        →  gateway  →  job service GET /jobs/<id>
       gateway returns {status, file_name, size} — never a path
```

### 3.4 Download

```
browser  GET /api/reports/<id>/download
       → Vercel fetches <gw>/v1/reports/<id>, reads download_url (signed, single-use)
       → Vercel fetches <gw>/dl/<signed>, gets workbook bytes
       → Vercel streams bytes to browser with Content-Disposition: attachment
```

---

## 4. How connectivity is established

### 4.1 Tailscale

- Node: `oracle-server`, tailnet IP `100.105.151.31`, DNS name
  `oracle-server.tail2b7fe2.ts.net`.
- Funnel is **on** for `https://oracle-server.tail2b7fe2.ts.net` (port 443) plus
  8443, 8791, 10000, 10001, 10004.

### 4.2 The 443 handler table (`tailscale serve status`)

```
https://oracle-server.tail2b7fe2.ts.net (Funnel on)
|-- /         proxy http://127.0.0.1:9119    ← Hermes UI
|-- /gw       proxy http://127.0.0.1:8790    ← REPORT GATEWAY  ★
|-- /api/v1   proxy http://127.0.0.1:9135/api/v1
|-- /auth/v1  proxy http://127.0.0.1:8877/auth/v1
|-- /rest/v1  proxy http://127.0.0.1:8877/rest/v1
|-- /session/ proxy http://127.0.0.1:9135/session/
|-- /__hermes proxy http://127.0.0.1:9121
```

★ The gateway was added as a **sub-path of the existing public 443 funnel** rather than
as its own public port, because funnel only works on 443/8443/10000-family ports and
all of those were already in use by other services. `tailscale serve` strips the `/gw`
prefix before proxying, so the gateway still sees `/v1/config` — no code change needed.

**Public gateway endpoint:**

```
https://oracle-server.tail2b7fe2.ts.net/gw
```

The gateway itself listens on `127.0.0.1:8790` only — it is **not** bound to the tailnet
IP and is not directly reachable from outside. The funnel is the only public ingress.

### 4.3 Vercel → VPS

Vercel's serverless functions call the public funnel URL over HTTPS with the
`x-report-token` header. No VPN, no static IP, no tunnel client on the VPS.

### 4.4 Ports summary

| Port | Bind | Service | Public? |
|---|---|---|---|
| 8787 | 127.0.0.1 | job service | no |
| 8790 | 127.0.0.1 | report gateway | **yes, via 443 `/gw`** |
| 3011 | 127.0.0.1 | local Next.js (dev/preview) | no |
| 443 | tailnet IP | Tailscale Funnel | yes |

---

## 5. Authentication summary

| Hop | Credential | Transport |
|---|---|---|
| browser → Vercel | none (public app) | HTTPS |
| Vercel → gateway | `x-report-token: <app_token>` | HTTPS via funnel |
| gateway → job service | `Authorization: Bearer <job_token>` | HTTP on loopback |
| job service → portal | e-ShikshaKosh OTP/session via existing runners | HTTPS |

Only `/healthz` on the gateway and `/health` on the job service are unauthenticated.
Everything else is rejected without a valid token (401).

---

## 6. Full path reference

| Purpose | Path |
|---|---|
| Repository | `/home/prashant/projects/eshikshakosh-automation` |
| Gateway source | `shared/gateway/server.py` |
| Gateway config (0600, secret) | `shared/gateway/config.json` |
| Gateway launcher | `shared/gateway/run.sh` |
| Job service source | `shared/jobserver/server.py` |
| Job service launcher | `shared/jobserver/run.sh` |
| Web app | `web/` |
| Web env (committed) | `web/.env.example` |
| Web env (secret) | `web/.env.local` |
| Vercel metadata (local) | `web/.vercel/project.json` |
| Student runner | `~/.local/bin/eshikshakosh-report` |
| Protected secret wrapper | `~/.local/bin/eshikshakosh-run` |
| Teacher roster runner | `modules/teacher/run_teacher_report.sh` |
| Teacher detail runner | `modules/teacher/run_teacher_detail_report.sh` |
| Workbook output | `~/exports/`, `~/exports/student/`, `~/exports/student/archive/` |
| Job state | `~/.local/share/jobserver/jobs.json` |
| Job audit log | `~/.local/share/jobserver/audit.log` |
| Gateway unit | `~/.config/systemd/user/esk-gateway.service` |
| Job service unit | `~/.config/systemd/user/esk-jobserver.service` (template: `shared/jobserver/esk-jobserver.service`) |
| Job service token | `~/.config/systemd/user/esk-jobserver.env` (mode 0600, **not** committed) |
| Web unit | `~/.config/systemd/user/esk-web.service` |
| Python venv | `.venv/bin/python` |
| Node | `/home/prashant/.local/node/current/bin` |

### systemd units

`esk-gateway.service`:

```ini
[Unit]
Description=e-Shikshakosh report gateway (job queue + signed report delivery)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/prashant/projects/eshikshakosh-automation
ExecStart=/home/prashant/projects/eshikshakosh-automation/.venv/bin/python shared/gateway/server.py --host 127.0.0.1 --port 8790
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
```

`esk-web.service`:

```ini
[Unit]
Description=e-Shikshakosh Report Workbench (Next.js)
After=network-online.target esk-gateway.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/prashant/projects/eshikshakosh-automation/web
EnvironmentFile=/home/prashant/projects/eshikshakosh-automation/web/.env.local
Environment=PATH=/home/prashant/.local/node/current/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/home/prashant/projects/eshikshakosh-automation/web/node_modules/.bin/next start -p 3011 -H 127.0.0.1
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
```

Enable with `systemctl --user enable --now esk-gateway.service esk-web.service`.

---

## 7. Verification recipe

Run these before claiming anything works. All should be run on the VPS.

```bash
# 1. services up
systemctl --user is-active esk-gateway.service esk-web.service

# 2. local listeners
ss -tlnp | grep -E '8787|8790|3011'

# 3. gateway liveness (public, no token — must be 200)
curl -s -o /dev/null -w '%{http_code}\n' https://oracle-server.tail2b7fe2.ts.net/gw/healthz

# 4. auth enforced (must be 401, both with no token and a bogus token)
curl -s -o /dev/null -w '%{http_code}\n' https://oracle-server.tail2b7fe2.ts.net/gw/v1/config
curl -s -o /dev/null -w '%{http_code}\n' -H 'x-report-token: deadbeef' \
  https://oracle-server.tail2b7fe2.ts.net/gw/v1/config

# 5. funnel table intact (all 7 handlers on 443, funnel on)
tailscale serve status | sed -n '/oracle-server.tail2b7fe2.ts.net (Funnel/,/^$/p'
tailscale funnel status | head -8

# 6. full path through Vercel (expects a real workbook)
curl -s https://eshikshakosh-coral.vercel.app/api/config
```

End-to-end job test (start → poll → download) should be done through the Vercel UI or
by replaying the four route calls with a valid `ESK_GATEWAY_TOKEN`.

---

## 8. Known gaps and risks

| # | Finding | Severity | Action |
|---|---|---|---|
| 1 | ~~Job service not a systemd unit~~ — **RESOLVED 2026-10-23.** It was a manually-started Hermes exec session (pid 2474042), so it died with that session. It is now `esk-jobserver.service` — template committed at `shared/jobserver/esk-jobserver.service`, `enable`d so it survives reboot, and verified end-to-end through the public funnel. | — | To rebuild: create `~/.config/systemd/user/esk-jobserver.env` containing `JOB_SERVER_TOKEN=<secret>` (mode 0600), copy the template into `~/.config/systemd/user/`, then `systemctl --user daemon-reload && systemctl --user enable --now esk-jobserver`. |
| 2 | **`job_token` in `shared/gateway/config.json` is a weak, guessable literal** (a `test-…` placeholder, ~14 chars). Anyone who reads the file can forge job-service requests. | **High** | Replace with a high-entropy secret, store in the protected secret wrapper, and reference by env var. |
| 3 | **The gateway is reachable from the public internet** at `/gw`. It is gated by `app_token`, but the surface exists. | Medium | Acceptable, or restrict funnel to specific paths / add allowlist. Consider whether the app should use the tailnet-only `:3011` URL instead of the public funnel. |
| 4 | ~~`web/.env.local` was mode `0644`~~ — **RESOLVED 2026-10-23** (`chmod 600`). Note the file is gitignored, so this is a local-only fix and must be reapplied on a fresh clone. | — | `chmod 600 web/.env.local`. |
| 5 | ~~Stale docs~~ — **RESOLVED 2026-10-23.** `ARCHITECTURE.md`, `WEB-DEPLOYMENT.md`, `REMOTE-ACCESS.md`, `web/README.md` and `docs/current-status.md` now carry a "superseded" banner pointing here, and the root `README.md` + `AGENTS.md` link to this file. | — | Keep the banners if those docs are rewritten. |
| 6 | ~~Uncommitted work~~ — **RESOLVED 2026-10-23.** Gateway, job service, web API routes, the handoff doc and the doc banners are committed and pushed to `main`. `shared/gateway/config.json` is now gitignored. `excel_to_pdf.py` and `generate_teacher_pdf.py` remain untracked (unrelated user scripts). | — | Decide separately whether those two scripts belong in the repo. |
| 7 | Job service rate limit is per-IP; behind the funnel all Vercel traffic may share egress IPs. | Low | Watch for 429s under real load. |

---

## 9. Pitfalls that cost real time (do not repeat)

1. **`tailscale serve --bg <port>` (bare port) clobbers the 443 `/` handler and turns off
   funnel on 443.** Always pass `--https=<port>` explicitly.
2. **`tailscale serve --set-path` on 443 removes the funnel flag.** Re-enable with
   `tailscale funnel --bg --https=443 http://127.0.0.1:9119`.
3. **Next.js must bind `127.0.0.1`** (`next start -p 3011 -H 127.0.0.1`). If it binds the
   tailnet IP it occupies the address and blocks Tailscale's listener.
4. **Re-applying `tailscale serve --bg --https=<port> …` forces the IPv4 rebind** — the
   recovery path when the listener looks wedged.
5. **Funnel only works on 443/8443/10000-family ports.** Cloudflare *named* tunnels need
   an account (none on this machine); quick tunnels get a new URL every start.
6. **The gateway auth header is `x-report-token`, not `Authorization: Bearer`.** The
   `Bearer` scheme is used only on the gateway→job-service hop. Mixing these up yields 401s
   that look like a wrong secret.
7. **`config.json` holds real secrets and is `0600`.** Never `cat` it into chat, never
   commit it, never paste its values into docs.

---

## 10. Do NOT

- Do not expose the job-service port (8787) publicly, and do not bind it to anything but
  `127.0.0.1`.
- Do not put portal credentials, tokens, or workbook bytes in any log, doc, or chat message.
- Do not call the e-ShikshaKosh portal from the browser, and do not have the browser talk
  to the job service directly — the gateway is the only public ingress by design.
- Do not remove the `x-report-token` check or the `allow_public` guard.
- Do not commit `shared/gateway/config.json`, `web/.env.local`, `web/.vercel/`, or any
  exported workbook.
- Do not replace the verified local runners with ad-hoc scraping.
- Do not treat this document as a substitute for checking live state — run §7 first.
