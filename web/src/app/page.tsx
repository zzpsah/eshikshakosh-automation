"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/* ------------------------------------------------------------------ */
/* Types — the shape is owned by the gateway, this only mirrors it.     */
/* ------------------------------------------------------------------ */

type School = { key: string; label: string; udise: string };
type Workflow = { name: string; tag: string; scope: string };
type Workflows = Record<string, Workflow>;

type Config = {
  schools: School[];
  workflows: Workflows;
  classes: string[];
  modes: string[];
  session: string;
  download_ttl: number;
};

type Job = {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  workflow: string;
  file_name: string | null;
  file_bytes: number | null;
  error?: string;
  log?: string;
};

const WORKFLOW_ORDER = ["student", "roster", "detail"] as const;
const WORKFLOW_GROUP: Record<string, string> = {
  student: "Student",
  roster: "Teacher",
  detail: "Teacher",
};
const WORKFLOW_SUMMARY: Record<string, string> = {
  student:
    "Class-scoped student workbook for one school, built from the e-ShikshaKosh OTR data.",
  roster:
    "One row per teacher with readable labels and a combined address, for the selected school.",
  detail:
    "Seven sheets per teacher — registration, education, professional, other, training and service history.",
};
const WORKFLOW_SCOPE: Record<string, string> = {
  student: "Classes 9-12 · class / privacy filters",
  roster: "All teachers of the selected school",
  detail: "All teachers of the selected school",
};
const WORKFLOW_CAUTION: Record<string, string> = {
  student:
    "Student records include Aadhaar, bank and contact fields. The workbook is personal data — keep it private.",
  roster: "The roster carries mobile, PAN and Aadhaar values. Treat it as personal data.",
  detail:
    "Service history can include previous postings. Verify before sharing outside the school.",
};

const CLASS_LABELS: Record<string, string> = {
  "": "All classes",
  "9": "Class 9",
  "10": "Class 10",
  "11": "Class 11",
  "12": "Class 12",
};

const STATUS_LABEL: Record<Job["status"], string> = {
  queued: "Queued",
  running: "Running",
  done: "Ready",
  failed: "Failed",
};

const POLL_MS = 3000;

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function formatBytes(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function ErrorNote({ message }: { message: string }) {
  return (
    <p className="job-error" role="alert">
      {message}
    </p>
  );
}

function RunnerLog({ log }: { log: string }) {
  return (
    <details className="job-log">
      <summary>Runner output</summary>
      <pre>{log}</pre>
    </details>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function Page() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [cfgError, setCfgError] = useState<string | null>(null);

  const [wf, setWf] = useState<string>("student");
  const [school, setSchool] = useState<string>("");
  const [cls, setCls] = useState<string>("");
  const [mode, setMode] = useState<string>("full");

  // Credentials. When both fields are filled the login is taken from the browser
  // for this run only; when left empty the runner uses the VPS vault.
  const [useManualCreds, setUseManualCreds] = useState(false);
  const [loginType, setLoginType] = useState<"school" | "teacher">("school");
  const [loginId, setLoginId] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  /* ---------------- config ---------------- */

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch("/api/config", { cache: "no-store" });
        const data = await res.json();
        if (cancelled) return;
        if (!res.ok) {
          setCfgError(data.error ?? "Could not reach the report gateway.");
          return;
        }
        setCfg(data as Config);
        setCfgError(null);
        setSchool((prev) => prev || (data.schools[0]?.key ?? ""));
      } catch {
        if (!cancelled) setCfgError("Could not reach the report gateway.");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  /* ---------------- polling ---------------- */

  const stopPolling = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const poll = useCallback(
    async (id: string) => {
      stopPolling();
      const tick = async () => {
        try {
          const res = await fetch(`/api/reports/${id}`, { cache: "no-store" });
          const data = await res.json();
          if (!res.ok) {
            setNotice(data.error ?? "Could not read the job status.");
            setBusy(false);
            return;
          }
          setJob(data as Job);
          if (data.status === "queued" || data.status === "running") {
            timer.current = setTimeout(tick, POLL_MS);
          } else {
            setBusy(false);
            if (data.status === "failed") {
              setNotice(data.error ?? "The report run failed.");
            }
          }
        } catch {
          setNotice("Lost contact with the report gateway.");
          setBusy(false);
        }
      };
      await tick();
    },
    [stopPolling],
  );

  useEffect(() => stopPolling, [stopPolling]);

  /* ---------------- actions ---------------- */

  async function generate() {
    setNotice(null);
    setBusy(true);
    setJob(null);

    const payload: Record<string, unknown> = { workflow: wf };
    if (wf === "student") {
      payload.class = cls;
      payload.mode = mode;
      if (cfg?.session) payload.session = cfg.session;
    } else {
      payload.school = school;
    }
    if (useManualCreds && loginId.trim() && loginPassword) {
      payload.username = loginId.trim();
      payload.password = loginPassword;
    }

    try {
      const res = await fetch("/api/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setNotice(data.error ?? "The report could not be started.");
        setBusy(false);
        return;
      }
      setJob(data as Job);
      await poll(data.id);
    } catch {
      setNotice("Could not reach the report gateway.");
      setBusy(false);
    }
  }

  /* ---------------- derived ---------------- */

  const inFlight = job?.status === "queued" || job?.status === "running";
  const ready = job?.status === "done";
  const schoolLabel =
    cfg?.schools.find((s) => s.key === school)?.label ?? "—";
  const credSource =
    useManualCreds && loginId.trim() && loginPassword
      ? "Entered for this run"
      : "VPS vault";

  return (
    <div className="shell">
      {/* ---------------- rail ---------------- */}
      <aside className="rail">
        <div className="brand">
          <span className="brand-mark">SD</span>
          <span className="brand-text">
            <strong>School Data Desk</strong>
            <span>e-ShikshaKosh reports</span>
          </span>
        </div>

        <nav className="rail-nav" aria-label="Sections">
          <span className="rail-label">Report centre</span>
          <a className="rail-link" href="#workbench" aria-current="true">
            Workbench
          </a>
          <a className="rail-link" href="#reference">
            Reference
          </a>
          <a className="rail-link" href="#safety">
            Safety
          </a>
        </nav>

        <div className="rail-foot">
          <dl>
            <div className="rail-foot-row">
              <dt>Gateway</dt>
              <dd>
                {cfgError ? (
                  <span className="state-bad">offline</span>
                ) : cfg ? (
                  <span className="state-ok">connected</span>
                ) : (
                  "checking"
                )}
              </dd>
            </div>
            <div className="rail-foot-row">
              <dt>Access</dt>
              <dd>Read-only</dd>
            </div>
            <div className="rail-foot-row">
              <dt>Credentials</dt>
              <dd>{credSource}</dd>
            </div>
          </dl>
        </div>
      </aside>

      {/* ---------------- main ---------------- */}
      <div className="main">
        <header className="topbar">
          <nav className="crumbs" aria-label="Breadcrumb">
            <span>e-ShikshaKosh</span>
            <span>/</span>
            <strong>Report centre</strong>
          </nav>
          <div className="topbar-meta">
            <span className="chip chip-ok">
              <span className="dot dot-ok" />
              Read-only
            </span>
            {cfgError ? (
              <span className="chip chip-warn">
                <span className="dot dot-warn" />
                Gateway offline
              </span>
            ) : (
              <span className="chip chip-ok">
                <span className="dot dot-ok" />
                Gateway live
              </span>
            )}
          </div>
        </header>

        <div className="body">
          <div className="context">
            <h1>Report workbench</h1>
            <p>
              Pick a workflow, set the school, and generate the workbook. Reports
              are built on the Oracle VPS and delivered to this page — no command
              line needed.
            </p>
          </div>

          {/* ---------------- workbench ---------------- */}
          <div className="workbench" id="workbench">
            <section className="panel" aria-label="Workflows">
              <div className="wf-list-head">
                <span className="eyebrow">Workflows</span>
                <strong>Choose one</strong>
              </div>
              <div className="wf-list" role="group" aria-label="Workflow">
                {cfg &&
                  WORKFLOW_ORDER.filter((id) => cfg.workflows[id]).map((id) => (
                    <button
                      key={id}
                      type="button"
                      className="wf-row"
                      aria-pressed={wf === id}
                      onClick={() => {
                        setWf(id);
                        setJob(null);
                        setNotice(null);
                      }}
                    >
                      <span>
                        <span className="wf-row-name">{cfg.workflows[id].name}</span>
                        <span className="wf-row-meta">
                          {WORKFLOW_GROUP[id] ?? ""}
                        </span>
                      </span>
                      <span className="wf-row-tag">{cfg.workflows[id].tag}</span>
                    </button>
                  ))}
                {!cfg && !cfgError && (
                  <p className="hint" style={{ padding: "12px 14px" }}>
                    Loading workflows…
                  </p>
                )}
              </div>
            </section>

            <section className="panel" aria-label="Generate report">
              <div className="action-head">
                <div>
                  <span className="eyebrow">{WORKFLOW_GROUP[wf] ?? "Report"}</span>
                  <h3>{cfg?.workflows[wf]?.name ?? "Report"}</h3>
                  <p>{WORKFLOW_SUMMARY[wf]}</p>
                </div>
              </div>

              <div className="action-body">
                {cfgError && <ErrorNote message={cfgError} />}

                {wf === "student" ? (
                  <div className="field-row">
                    <div className="field">
                      <label htmlFor="cls">Class</label>
                      <select
                        id="cls"
                        value={cls}
                        onChange={(e) => setCls(e.target.value)}
                      >
                        {(cfg?.classes ?? [""]).map((c) => (
                          <option key={c || "all"} value={c}>
                            {CLASS_LABELS[c] ?? c}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label id="mode-label">Privacy mode</label>
                      <div
                        className="segmented"
                        role="group"
                        aria-labelledby="mode-label"
                      >
                        {(cfg?.modes ?? ["full"]).map((m) => (
                          <button
                            key={m}
                            type="button"
                            aria-pressed={mode === m}
                            onClick={() => setMode(m)}
                          >
                            {m === "full" ? "Full" : m === "masked" ? "Masked" : m}
                          </button>
                        ))}
                      </div>
                      <span className="hint">
                        Masked hides Aadhaar, bank and contact values.
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="field">
                    <label htmlFor="school">School</label>
                    <select
                      id="school"
                      value={school}
                      onChange={(e) => setSchool(e.target.value)}
                    >
                      {(cfg?.schools ?? []).map((s) => (
                        <option key={s.key} value={s.key}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                    <span className="hint">
                      {schoolLabel} · UDISE{" "}
                      {cfg?.schools.find((s) => s.key === school)?.udise ?? "—"}
                    </span>
                  </div>
                )}

                <section className="panel cred-panel" aria-label="Portal login">
                  <div className="cred-head">
                    <div>
                      <span className="eyebrow">Portal login</span>
                      <h3>Credentials</h3>
                      <p>
                        By default the runner signs in with the credentials stored
                        in the VPS vault. Enter them here instead to run once with
                        a different login.
                      </p>
                    </div>
                    <div
                      className="segmented"
                      role="group"
                      aria-label="Credential source"
                    >
                      <button
                        type="button"
                        aria-pressed={!useManualCreds}
                        onClick={() => setUseManualCreds(false)}
                      >
                        VPS vault
                      </button>
                      <button
                        type="button"
                        aria-pressed={useManualCreds}
                        onClick={() => setUseManualCreds(true)}
                      >
                        Enter once
                      </button>
                    </div>
                  </div>

                  {useManualCreds && (
                    <div className="cred-body">
                      <div className="field">
                        <label id="login-type-label">Login type</label>
                        <div
                          className="segmented"
                          role="group"
                          aria-labelledby="login-type-label"
                        >
                          <button
                            type="button"
                            aria-pressed={loginType === "school"}
                            onClick={() => setLoginType("school")}
                          >
                            School · UDISE
                          </button>
                          <button
                            type="button"
                            aria-pressed={loginType === "teacher"}
                            onClick={() => setLoginType("teacher")}
                          >
                            Teacher ID
                          </button>
                        </div>
                        <span className="hint">
                          {loginType === "school"
                            ? "The 11-digit UDISE code of the school."
                            : "The 12-digit Teacher ID issued by the portal."}
                        </span>
                      </div>

                      <div className="field">
                        <label htmlFor="login-id">
                          {loginType === "school" ? "UDISE code" : "Teacher ID"}
                        </label>
                        <input
                          id="login-id"
                          inputMode="numeric"
                          autoComplete="off"
                          spellCheck={false}
                          value={loginId}
                          onChange={(e) => setLoginId(e.target.value)}
                          placeholder={
                            loginType === "school"
                              ? "11-digit UDISE code"
                              : "12-digit Teacher ID"
                          }
                        />
                      </div>

                      <div className="field">
                        <label htmlFor="login-password">Password</label>
                        <div className="pw-wrap">
                          <input
                            id="login-password"
                            type={showPassword ? "text" : "password"}
                            autoComplete="off"
                            value={loginPassword}
                            onChange={(e) => setLoginPassword(e.target.value)}
                            placeholder="Portal password"
                          />
                          <button
                            type="button"
                            className="pw-toggle"
                            aria-label={
                              showPassword ? "Hide password" : "Show password"
                            }
                            onClick={() => setShowPassword((v) => !v)}
                          >
                            {showPassword ? "Hide" : "Show"}
                          </button>
                        </div>
                        <span className="hint">
                          Used for this run only. Never stored or logged.
                        </span>
                      </div>
                    </div>
                  )}
                </section>

                <div className="job" aria-live="polite">
                  <div className="job-head">
                    <span className="eyebrow">Job</span>
                    <strong>
                      {job
                        ? STATUS_LABEL[job.status]
                        : busy
                          ? "Starting"
                          : "Idle"}
                    </strong>
                  </div>

                  {!job && !busy && (
                    <p className="hint">
                      Nothing running. Choose the options above and generate.
                    </p>
                  )}

                  {busy && !job && <p className="hint">Contacting the gateway…</p>}

                  {inFlight && (
                    <div className="job-progress">
                      <span className="spinner" aria-hidden="true" />
                      <span>
                        The report is being built on the VPS. This usually takes a
                        minute or two.
                      </span>
                    </div>
                  )}

                  {job && (
                    <dl className="job-meta">
                      <div style={{ display: "contents" }}>
                        <dt>Workflow</dt>
                        <dd>{cfg?.workflows[job.workflow]?.name ?? job.workflow}</dd>
                      </div>
                      <div style={{ display: "contents" }}>
                        <dt>File</dt>
                        <dd>{job.file_name ?? "pending"}</dd>
                      </div>
                      {job.file_bytes ? (
                        <div style={{ display: "contents" }}>
                          <dt>Size</dt>
                          <dd>{formatBytes(job.file_bytes)}</dd>
                        </div>
                      ) : null}
                      <div style={{ display: "contents" }}>
                        <dt>Job</dt>
                        <dd>
                          <code>{job.id}</code>
                        </dd>
                      </div>
                    </dl>
                  )}

                  {ready && job.file_name && (
                    <a
                      className="btn-primary"
                      href={`/api/reports/${job.id}/download`}
                      download
                    >
                      Download {job.file_name}
                    </a>
                  )}

                  {job?.status === "failed" && (
                    <ErrorNote message={job.error ?? "The report run failed."} />
                  )}

                  {job?.status === "failed" && job.log ? (
                    <RunnerLog log={job.log} />
                  ) : null}

                  {notice && <ErrorNote message={notice} />}
                </div>

                <div className="job-actions">
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={generate}
                    disabled={!cfg || busy || inFlight}
                  >
                    {inFlight ? "Running…" : job ? "Run again" : "Generate report"}
                  </button>
                  {job && (ready || job.status === "failed") && (
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() => {
                        setJob(null);
                        setNotice(null);
                      }}
                    >
                      Clear
                    </button>
                  )}
                </div>

                <dl className="facts">
                  <div style={{ display: "contents" }}>
                    <dt>Scope</dt>
                    <dd>{WORKFLOW_SCOPE[wf]}</dd>
                  </div>
                  <div style={{ display: "contents" }}>
                    <dt>Session</dt>
                    <dd>{cfg?.session ?? "—"}</dd>
                  </div>
                  <div style={{ display: "contents" }}>
                    <dt>Credentials</dt>
                    <dd>{credSource}</dd>
                  </div>
                </dl>

                <div className="caution">
                  <strong>Handle with care</strong>
                  <p>{WORKFLOW_CAUTION[wf]}</p>
                </div>
              </div>
            </section>
          </div>

          {/* ---------------- reference ---------------- */}
          <section className="ref" id="reference" aria-label="Reference">
            <div className="sec-head">
              <h2>All workflows</h2>
              <span className="sec-note">What each report contains</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Workflow</th>
                    <th scope="col">Scope</th>
                    <th scope="col">Group</th>
                    <th scope="col">Privacy</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(cfg?.workflows ?? {}).map(([id, w]) => (
                    <tr key={id}>
                      <td className="wf">{w.name}</td>
                      <td>{w.scope}</td>
                      <td>{WORKFLOW_GROUP[id] ?? "—"}</td>
                      <td>
                        {id === "student"
                          ? "Full or masked"
                          : "As published by the portal"}
                      </td>
                    </tr>
                  ))}
                  {!cfg && (
                    <tr>
                      <td colSpan={4}>Loading…</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {/* ---------------- safety ---------------- */}
          <section className="safety" id="safety" aria-label="Safety">
            <div>
              <h3>Read-only by design</h3>
              <p>
                Every workflow only reads from the portal. Nothing is written back
                to e-ShikshaKosh.
              </p>
            </div>
            <div>
              <h3>Credentials are never stored</h3>
              <p>
                By default the runners read them from the VPS vault at runtime. If
                you enter them here they are used for that run only and are never
                stored in this app, in Vercel, or in this repository.
              </p>
            </div>
            <div>
              <h3>Delivery stays private</h3>
              <p>
                The app calls the private report gateway over an authenticated
                tunnel. Download links are single-use and expire quickly.
              </p>
            </div>
          </section>

          <footer className="foot">
            <span>School Data Desk · e-ShikshaKosh automation repository</span>
            <span>Read-only · Oracle VPS</span>
          </footer>
        </div>
      </div>
    </div>
  );
}
