"use client";

import { useState } from "react";
import Link from "next/link";

export default function Home() {
  const [schoolCode, setSchoolCode] = useState("");
  const [session, setSession] = useState("2026-27");
  const [reportType, setReportType] = useState("all");
  const [status, setStatus] = useState("");

  async function requestReport(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("Report service is not connected yet. No portal request was sent.");
  }

  return (
    <main className="shell">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="eShikshaKosh reports home">
          <span className="brand-mark">eK</span>
          <span><strong>eShikshaKosh</strong><small>REPORT DOWNLOADER</small></span>
        </Link>
        <span className="secure"><span className="secure-dot" /> Private workspace</span>
      </header>

      <section className="hero">
        <div className="eyebrow"><span /> SCHOOL DATA · READ-ONLY</div>
        <h1>Your school reports,<br /><em>ready when you are.</em></h1>
        <p className="hero-copy">Generate an Excel student-details report from eShikshaKosh using the existing verified report workflow.</p>
      </section>

      <section className="workspace">
        <div className="panel-head">
          <div><div className="step">REPORT BUILDER <span>01</span></div><h2>Prepare a report</h2><p>Choose the school and reporting options below.</p></div>
          <div className="file-icon" aria-hidden="true">XLSX</div>
        </div>
        <form onSubmit={requestReport}>
          <label htmlFor="schoolCode">School code / UDISE code <span className="optional">Optional</span></label>
          <input id="schoolCode" value={schoolCode} onChange={(e) => setSchoolCode(e.target.value)} placeholder="Enter the authorized school code" autoComplete="off" />
          <div className="field-grid">
            <div><label htmlFor="session">Academic session</label><select id="session" value={session} onChange={(e) => setSession(e.target.value)}><option>2026-27</option><option>2025-26</option><option>2024-25</option></select></div>
            <div><label htmlFor="reportType">Report scope</label><select id="reportType" value={reportType} onChange={(e) => setReportType(e.target.value)}><option value="all">All students</option><option value="class10">Class 10</option><option value="class11">Class 11</option><option value="class12">Class 12</option></select></div>
          </div>
          <div className="notice"><span className="notice-icon">i</span><p><strong>Privacy first</strong><br />Reports may contain sensitive student information. Downloads will be available only after private access and backend authentication are configured.</p></div>
          <button type="submit">Generate Excel report <span aria-hidden="true">↗</span></button>
          {status && <p className="status" role="status">{status}</p>}
        </form>
      </section>

      <section className="feature-row">
        <article><span className="feature-symbol">↻</span><div><h3>Existing workflow</h3><p>Uses the repository’s established report generator, not a new scraper.</p></div></article>
        <article><span className="feature-symbol">▣</span><div><h3>Excel output</h3><p>Workbook download, with no student records shown in the browser.</p></div></article>
        <article><span className="feature-symbol">⌑</span><div><h3>Read-only access</h3><p>No portal edits, submissions, certification, or deletion.</p></div></article>
      </section>
      <footer><span>eShikshaKosh Report Downloader</span><span>Independent service · Not affiliated with the portal</span></footer>
    </main>
  );
}
