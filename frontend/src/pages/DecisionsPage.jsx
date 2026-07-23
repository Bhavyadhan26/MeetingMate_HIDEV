import { useState } from "react";
import { DecisionCard } from "../components/DecisionCard.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { useDecisions } from "../hooks/useDecisions.js";

export default function DecisionsPage({ appState }) {
  const [filters, setFilters] = useState({ query: "", sort: "newest", status: "all" });
  const decisions = useDecisions(appState.decisions, filters);
  const statuses = ["all", "active", "conflicted", "resolved", "superseded"];
  const latestMeeting = appState.meetings[0];
  const latestSummary = appState.activities[0];

  return (
    <>
      <section className="meeting-report-shell">
        <div className="report-main">
          <section className="report-card report-title-card">
            <div>
              <h1>{latestMeeting?.title || "Meeting Details & Audit Report"}</h1>
              <p>{latestMeeting ? `${latestMeeting.team_id} | ${latestMeeting.trace_id}` : "Verified transcript and decision audit"}</p>
            </div>
            <div className="report-score">
              <span>Audit Score</span>
              <strong>{decisions.length ? "98.4%" : "0%"}</strong>
            </div>
          </section>
          <section className="report-grid">
            <article className="report-card ai-summary-card">
              <h3><span className="material-symbols-outlined">auto_awesome</span> AI Summary</h3>
              <p>{latestSummary?.text || "Process a meeting to generate a grounded audit report. Decision source excerpts and drift flags appear here after extraction."}</p>
            </article>
            <article className="report-card action-strip">
              <h3>Action Items</h3>
              {(appState.actions.length ? appState.actions : [{ task: "No action items extracted yet" }]).slice(0, 4).map((item, index) => (
                <p key={`${item.task}-${index}`}><span className="material-symbols-outlined">check_circle</span>{item.task}</p>
              ))}
            </article>
          </section>
          <section className="report-card transcript-card">
            <div className="panel-header">
              <h3>Verified Transcript</h3>
              <div className="inline-actions">
                <button className="secondary-button" type="button"><span className="material-symbols-outlined">filter_list</span> Filter</button>
                <button className="secondary-button" type="button"><span className="material-symbols-outlined">download</span> Export</button>
              </div>
            </div>
            <div className="transcript-block">
              <div>
                <span>[PERSON_1] | AUDIT_LEAD</span>
                <small>00:04:12</small>
              </div>
              <p>Regarding the meeting baseline, the system extracted decisions and matched them against the organizational memory ledger. Highlighted excerpts require auditor verification before downstream use.</p>
            </div>
            <div className="transcript-block">
              <div>
                <span>[PERSON_2] | DECISION_OWNER</span>
                <small>00:05:45</small>
              </div>
              <p>Potential drift is identified when a new decision conflicts with a prior active grounding. Resolve or supersede the prior record to restore ledger consistency.</p>
            </div>
          </section>
        </div>
        <aside className="report-rail">
          <section className="report-card">
            <div className="panel-header">
              <h3>New Decisions</h3>
              <span className="badge active">{decisions.length}</span>
            </div>
            <input className="compact-input" onChange={(event) => setFilters((value) => ({ ...value, query: event.target.value }))} placeholder="Search decisions" value={filters.query} />
            <div className="toolbar compact-toolbar">
              {statuses.map((status) => (
                <button className={`chip ${filters.status === status ? "active" : ""}`} key={status} onClick={() => setFilters((value) => ({ ...value, status }))} type="button">
                  {status}
                </button>
              ))}
            </div>
            <select className="compact-input" onChange={(event) => setFilters((value) => ({ ...value, sort: event.target.value }))} value={filters.sort}>
              <option value="newest">Newest</option>
              <option value="status">Status</option>
              <option value="drift">Drift label</option>
            </select>
          </section>
          <section className="report-card decision-rail-list">
            {!decisions.length ? (
              <EmptyState title="No decisions have been extracted yet" message="Upload a meeting to get started." />
            ) : decisions.slice(0, 10).map((decision) => <DecisionCard decision={decision} key={decision.id} />)}
          </section>
        </aside>
      </section>
    </>
  );
}
