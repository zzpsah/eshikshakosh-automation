"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

type ReportKind = "student" | "roster" | "profile";
type School = "Sahaspur" | "Tetahali";

const reports: Record<ReportKind, { title: string; eyebrow: string; description: string; command: (school: School) => string; steps: string[] }> = {
  student: {
    title: "Student details",
    eyebrow: "STUDENT REPORT",
    description: "Generate the existing student-details workbook through the authorised Oracle VPS workflow.",
    command: () => "~/.local/bin/eshikshakosh-report",
    steps: ["Run the command on the authorised Oracle VPS or through your approved Hermes workflow.", "Choose the school and any requested report filters when prompted.", "Review the generated workbook before sharing it."],
  },
  roster: {
    title: "Teacher roster",
    eyebrow: "TEACHER REPORT",
    description: "Export the teacher list and available profile fields for one registered school.",
    command: (school) => `modules/teacher/run_teacher_report.sh --school ${school}`,
    steps: ["Open the eshikshakosh-automation project on the Oracle VPS.", "Run the command below from the repository root.", "The timestamped Excel workbook is saved in ~/exports."],
  },
  profile: {
    title: "Full teacher profiles",
    eyebrow: "TEACHER DETAIL REPORT",
    description: "Export teacher registration details, education, professional qualifications, other information, training and service history.",
    command: (school) => `modules/teacher/run_teacher_detail_report.sh --school ${school}`,
    steps: ["Open the eshikshakosh-automation project on the Oracle VPS.", "Run the command below from the repository root.", "Check the workbook sheets and confirm empty sections against the portal before drawing conclusions."],
  },
};

export default function Home() {
  const [reportKind, setReportKind] = useState<ReportKind>("profile");
  const [school, setSchool] = useState<School>("Sahaspur");
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const selected = reports[reportKind];
  const command = useMemo(() => selected.command(school), [selected, school]);

  async function copyCommand() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setCopyError(false);
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      setCopied(false);
      setCopyError(true);
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/" aria-label="School Data Desk home">
          <span className="brand-symbol">SD</span>
          <span className="brand-copy"><strong>School Data Desk</strong><small>e-ShikshaKosh tools</small></span>
        </Link>
        <div className="nav-label">WORKSPACE</div>
        <a className="nav-item active" href="#reports"><span className="nav-icon">▤</span> Report centre <span className="nav-arrow">›</span></a>
        <a className="nav-item" href="#how-it-works"><span className="nav-icon">↗</span> How it works</a>
        <a className="nav-item" href="#safety"><span className="nav-icon">◇</span> Data & safety</a>
        <div className="sidebar-bottom">
          <span className="status-dot amber" />
          <div><strong>Portal connection</strong><small>Runner integration pending</small></div>
        </div>
      </aside>

      <section className="main-area">
        <header className="topbar">
          <div><span className="breadcrumb">Workspace</span><span className="crumb-sep">/</span><strong>Report centre</strong></div>
          <span className="environment"><span className="status-dot amber" /> Command guide</span>
        </header>

        <div className="content">
          <section className="welcome">
            <div className="welcome-copy">
              <div className="overline"><span className="overline-mark" /> SCHOOL OPERATIONS</div>
              <h1>School reports,<br /><em>without the guesswork.</em></h1>
              <p>Choose a verified report workflow, copy its command, and run it on the authorised Oracle VPS. This website does not sign in to e-ShikshaKosh or generate files by itself yet.</p>
            </div>
            <div className="welcome-art" aria-hidden="true">
              <div className="art-sheet"><div className="art-sheet-top" /><div className="art-line wide" /><div className="art-line" /><div className="art-line short" /><div className="art-grid"><i /><i /><i /><i /><i /><i /></div></div>
              <div className="art-check">✓</div>
            </div>
          </section>

          <section className="connection-banner" aria-label="Integration status">
            <span className="banner-icon">i</span>
            <div><strong>Report service is not connected to this website</strong><p>The existing scripts run on the Oracle VPS. No portal request is sent from this page, and no password or student/teacher personal data should be entered here.</p></div>
            <span className="status-pill">Not connected</span>
          </section>

          <section className="report-layout" id="reports">
            <div className="report-picker">
              <div className="section-heading"><div><span className="section-kicker">01 / SELECT A WORKFLOW</span><h2>What do you need?</h2></div><span className="count-badge">3 workflows</span></div>
              <div className="report-options">
                <button type="button" className={reportKind === "student" ? "report-option selected" : "report-option"} onClick={() => { setReportKind("student"); setCopied(false); }} aria-pressed={reportKind === "student"}>
                  <span className="option-icon student-icon">▦</span><span className="option-text"><strong>Student details</strong><small>Student report workbook</small></span><span className="option-chevron">›</span>
                </button>
                <button type="button" className={reportKind === "roster" ? "report-option selected" : "report-option"} onClick={() => { setReportKind("roster"); setCopied(false); }} aria-pressed={reportKind === "roster"}>
                  <span className="option-icon roster-icon">☷</span><span className="option-text"><strong>Teacher roster</strong><small>Teacher list and profile fields</small></span><span className="option-chevron">›</span>
                </button>
                <button type="button" className={reportKind === "profile" ? "report-option selected" : "report-option"} onClick={() => { setReportKind("profile"); setCopied(false); }} aria-pressed={reportKind === "profile"}>
                  <span className="option-icon profile-icon">▤</span><span className="option-text"><strong>Full teacher profiles</strong><small>Seven-sheet detail workbook</small></span><span className="option-chevron">›</span>
                </button>
              </div>
              <div className="picker-foot"><span className="status-dot green" /> Read-only workflow <span className="foot-separator">·</span> Excel output</div>
            </div>

            <div className="command-card">
              <div className="command-card-head"><div><span className="section-kicker">02 / WORKFLOW DETAILS</span><span className="type-label">{selected.eyebrow}</span><h2>{selected.title}</h2></div><span className="file-badge">XLSX</span></div>
              <p className="workflow-description">{selected.description}</p>
              {reportKind !== "student" && <div className="school-field"><label htmlFor="school">Registered school</label><select id="school" value={school} onChange={(e) => { setSchool(e.target.value as School); setCopied(false); }}><option value="Sahaspur">UMV Sahaspur</option><option value="Tetahali">UMV Tetahali</option></select><small>Uses the configured school alias and protected credential workflow.</small></div>}
              <div className="command-label"><span>COMMAND</span><span>Run on Oracle VPS</span></div>
              <div className="command-box"><code>{command}</code><button type="button" className="copy-button" onClick={copyCommand} aria-label="Copy command">{copied ? "Copied ✓" : "Copy"}</button></div>
              {copyError && <p className="copy-error" role="status">Clipboard access was blocked. Select and copy the command above manually.</p>}
              <div className="workflow-steps"><strong>Next steps</strong><ol>{selected.steps.map((step) => <li key={step}>{step}</li>)}</ol></div>
              <div className="not-run-note"><span>!</span><p><strong>This button does not generate a report.</strong> The live runner/API must be securely connected before in-browser generation can be enabled.</p></div>
            </div>
          </section>

          <section className="lower-grid" id="how-it-works">
            <article className="info-card"><span className="info-number">01</span><div><h3>Choose a workflow</h3><p>Select student details, teacher roster, or the full teacher profile workbook.</p></div></article>
            <article className="info-card"><span className="info-number">02</span><div><h3>Run it on the VPS</h3><p>The existing protected runner handles portal login, authorised school scope, and Excel export.</p></div></article>
            <article className="info-card" id="safety"><span className="info-number">03</span><div><h3>Review before sharing</h3><p>Exports can contain personal and employment information. Store them securely and share only with authorised recipients.</p></div></article>
          </section>

          <footer className="footer"><span>School Data Desk <span className="footer-muted">·</span> e-ShikshaKosh workflow helper</span><span>Independent utility · Not an official Bihar Government portal</span></footer>
        </div>
      </section>
    </main>
  );
}
