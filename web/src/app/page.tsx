"use client";

import { useState } from "react";

/* ------------------------------------------------------------------ */
/* Data — every value below is a real fact about the repository.       */
/* ------------------------------------------------------------------ */

const SCHOOLS = [
  { value: "Sahaspur", label: "UMV Sahaspur" },
  { value: "Tetahali", label: "UCHCH Madhyamik Vidyalaya Tetahali" },
];

const WORKFLOWS = [
  {
    id: "student",
    name: "Student details",
    group: "Student",
    tag: "OTR",
    summary:
      "Class, section or stream scoped student workbook for one school. Written to the repository root with mode 0600.",
    entry: "~/.local/bin/eshikshakosh-report",
    output: "Student_Details_<School>_<Session>.xlsx",
    scope: "Classes 9-12 · class / section / stream filters",
    facts: [
      ["Output", "Student_Details_<School>_<Session>.xlsx"],
      ["Scope", "Classes 9-12 · class / section / stream filters"],
      ["Privacy", "full or masked (default: full)"],
      ["Credentials", "Bitwarden, read-only"],
    ],
    steps: [
      "Run the command on the Oracle VPS.",
      "The runner asks for the session year, then the school.",
      "The workbook is written to the repository root, mode 0600.",
    ],
    caution:
      "Student records include Aadhaar, bank and contact fields. Keep the file inside the repository and never commit it.",
  },
  {
    id: "roster",
    name: "Teacher roster",
    group: "Teacher",
    tag: "LIST",
    summary:
      "One row per teacher with readable labels and a combined address. Built from the list API merged with registration info.",
    entry: "modules/teacher/run_teacher_report.sh",
    output: "~/exports/Teachers_<School>_browser_<timestamp>.xlsx",
    scope: "All teachers of the selected school",
    facts: [
      ["Output", "Teachers_<School>_browser_<timestamp>.xlsx"],
      ["Columns", "28 · labels, not raw codes"],
      ["Address", "single cell, labelled"],
      ["Credentials", "Bitwarden, read-only"],
    ],
    steps: [
      "Run the command on the Oracle VPS.",
      "Pick the school when prompted — it never assumes one.",
      "The runner logs in, captures the session and writes the workbook.",
    ],
    caution:
      "The roster carries mobile, PAN and Aadhaar values. Treat it as personal data.",
  },
  {
    id: "detail",
    name: "Full teacher profiles",
    group: "Teacher",
    tag: "DETAIL",
    summary:
      "Seven sheets per teacher: registration, education, professional, other, training and service history.",
    entry: "modules/teacher/run_teacher_detail_report.sh",
    output: "~/exports/Teacher_Details_<School>_<timestamp>.xlsx",
    scope: "All teachers of the selected school",
    facts: [
      ["Output", "Teacher_Details_<School>_<timestamp>.xlsx"],
      ["Sheets", "7 · Teachers, Registration, Education, Professional, Other, Training, Service"],
      ["Credentials", "Bitwarden, read-only"],
    ],
    steps: [
      "Run the command on the Oracle VPS.",
      "Pick the school when prompted — it never assumes one.",
      "Set ESHIKSHAKOSH_DETAIL_LIMIT=N to cap the run while testing.",
    ],
    caution:
      "Service history can include previous postings. Verify before sharing outside the school.",
  },
] as const;

type WorkflowId = (typeof WORKFLOWS)[number]["id"];

const REFERENCE = [
  {
    wf: "Student details",
    entry: "~/.local/bin/eshikshakosh-report",
    output: "Student_Details_<School>_<Session>.xlsx",
    scope: "Classes 9-12 · class / section / stream",
  },
  {
    wf: "Teacher roster",
    entry: "modules/teacher/run_teacher_report.sh --school <School>",
    output: "Teachers_<School>_browser_<timestamp>.xlsx",
    scope: "All teachers of the school",
  },
  {
    wf: "Full teacher profiles",
    entry: "modules/teacher/run_teacher_detail_report.sh --school <School>",
    output: "Teacher_Details_<School>_<timestamp>.xlsx",
    scope: "All teachers of the school",
  },
];

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function buildCommand(id: WorkflowId, school: string, cls: string, mode: string) {
  if (id === "student") {
    const parts = ["~/.local/bin/eshikshakosh-report"];
    if (cls !== "all") parts.push(`--class ${cls}`);
    if (mode === "masked") parts.push("--mode masked");
    return parts.join(" ");
  }
  const entry = WORKFLOWS.find((w) => w.id === id)!.entry;
  return `${entry} --school ${school}`;
}

function CopyButton({ text }: { text: string }) {
  const [state, setState] = useState<"idle" | "done" | "error">("idle");

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("done");
    } catch {
      setState("error");
    }
    window.setTimeout(() => setState("idle"), 1800);
  }

  return (
    <>
      <button
        type="button"
        className="copy"
        data-state={state === "done" ? "done" : undefined}
        onClick={copy}
      >
        {state === "done" ? "Copied" : "Copy"}
      </button>
      <p className="copy-note" aria-live="polite">
        {state === "error"
          ? "Clipboard blocked — select the command and copy it manually."
          : "Run this on the Oracle VPS. This page does not run reports."}
      </p>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function Page() {
  const [wf, setWf] = useState<WorkflowId>("student");
  const [school, setSchool] = useState(SCHOOLS[0].value);
  const [cls, setCls] = useState("all");
  const [mode, setMode] = useState<"full" | "masked">("full");

  const active = WORKFLOWS.find((w) => w.id === wf)!;
  const command = buildCommand(wf, school, cls, mode);

  return (
    <div className="shell">
      {/* ---------------- rail ---------------- */}
      <aside className="rail">
        <div className="brand">
          <span className="brand-mark">SD</span>
          <span className="brand-text">
            <strong>School Data Desk</strong>
            <span>e-ShikshaKosh workflows</span>
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
              <dt>Environment</dt>
              <dd>Oracle VPS</dd>
            </div>
            <div className="rail-foot-row">
              <dt>Access</dt>
              <dd>Read-only</dd>
            </div>
            <div className="rail-foot-row">
              <dt>Credentials</dt>
              <dd>Bitwarden</dd>
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
            <span className="chip chip-warn">
              <span className="dot dot-warn" />
              Not connected
            </span>
          </div>
        </header>

        <div className="body">
          {/* context line — replaces the old hero */}
          <div className="context">
            <h1>Report workbench</h1>
            <p>
              Pick a workflow, set the school, copy the command. Reports run on
              the Oracle VPS — this page only builds the command.
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
                {WORKFLOWS.map((w) => (
                  <button
                    key={w.id}
                    type="button"
                    className="wf-row"
                    aria-pressed={wf === w.id}
                    onClick={() => setWf(w.id)}
                  >
                    <span>
                      <span className="wf-row-name">{w.name}</span>
                      <span className="wf-row-meta">{w.group}</span>
                    </span>
                    <span className="wf-row-tag">{w.tag}</span>
                  </button>
                ))}
              </div>
            </section>

            <section className="panel" aria-label="Command">
              <div className="action-head">
                <div>
                  <span className="eyebrow">{active.group}</span>
                  <h3>{active.name}</h3>
                  <p>{active.summary}</p>
                </div>
              </div>

              <div className="action-body">
                {wf === "student" ? (
                  <div className="field-row">
                    <div className="field">
                      <label htmlFor="cls">Class</label>
                      <select
                        id="cls"
                        value={cls}
                        onChange={(e) => setCls(e.target.value)}
                      >
                        <option value="all">All classes</option>
                        <option value="9">Class 9</option>
                        <option value="10">Class 10</option>
                        <option value="11">Class 11</option>
                        <option value="12">Class 12</option>
                      </select>
                    </div>
                    <div className="field">
                      <label id="mode-label">Privacy mode</label>
                      <div
                        className="segmented"
                        role="group"
                        aria-labelledby="mode-label"
                      >
                        <button
                          type="button"
                          aria-pressed={mode === "full"}
                          onClick={() => setMode("full")}
                        >
                          Full
                        </button>
                        <button
                          type="button"
                          aria-pressed={mode === "masked"}
                          onClick={() => setMode("masked")}
                        >
                          Masked
                        </button>
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
                      {SCHOOLS.map((s) => (
                        <option key={s.value} value={s.value}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                    <span className="hint">
                      The runner always asks — it never assumes a school.
                    </span>
                  </div>
                )}

                <div>
                  <div className="cmd-label">
                    <span>Command</span>
                    <em>Oracle VPS · bash</em>
                  </div>
                  <div className="cmd">
                    <code>
                      <b>$</b> {command}
                    </code>
                    <CopyButton text={command} />
                  </div>
                </div>

                <dl className="facts">
                  {active.facts.map(([k, v]) => (
                    <div key={k} style={{ display: "contents" }}>
                      <dt>{k}</dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>

                <div>
                  <span className="eyebrow">Before you run</span>
                  <ol className="steps">
                    {active.steps.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ol>
                </div>

                <div className="caution">
                  <strong>Handle with care</strong>
                  <p>{active.caution}</p>
                </div>
              </div>
            </section>
          </div>

          {/* ---------------- reference ---------------- */}
          <section className="ref" id="reference" aria-label="Reference">
            <div className="sec-head">
              <h2>All workflows</h2>
              <span className="sec-note">
                Entry points and outputs, at a glance
              </span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Workflow</th>
                    <th scope="col">Entry point</th>
                    <th scope="col">Output</th>
                    <th scope="col">Scope</th>
                  </tr>
                </thead>
                <tbody>
                  {REFERENCE.map((r) => (
                    <tr key={r.wf}>
                      <td className="wf">{r.wf}</td>
                      <td>
                        <code>{r.entry}</code>
                      </td>
                      <td>{r.output}</td>
                      <td>{r.scope}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* ---------------- safety ---------------- */}
          <section className="safety" id="safety" aria-label="Safety">
            <div>
              <h3>Read-only by design</h3>
              <p>
                Every workflow only reads from the portal. Nothing is written
                back to e-ShikshaKosh.
              </p>
            </div>
            <div>
              <h3>Credentials stay in Bitwarden</h3>
              <p>
                The runners read them at runtime. No password is stored in this
                repository or on this page.
              </p>
            </div>
            <div>
              <h3>Not connected</h3>
              <p>
                This page cannot reach the portal. Copy the command and run it
                on the Oracle VPS.
              </p>
            </div>
          </section>

          <footer className="foot">
            <span>
              School Data Desk · e-ShikshaKosh automation repository
            </span>
            <span>Read-only · Bitwarden · Oracle VPS</span>
          </footer>
        </div>
      </div>
    </div>
  );
}
