import { ActivityFeed } from "../components/ActivityFeed.jsx";
import { DriftChart } from "../components/DriftChart.jsx";
import { MetricCard } from "../components/MetricCard.jsx";

export default function DashboardPage({ appState }) {
  const activeDecisions = appState.decisions.filter((decision) => decision.status === "active").length;
  const conflictedDecisions = appState.decisions.filter((decision) => decision.status === "conflicted").length;
  const latestMeeting = appState.meetings[0];
  const recentMeetings = appState.meetings.slice(0, 6);
  const conflicts = appState.decisions.filter((decision) => decision.status === "conflicted").slice(0, 2);
  return (
    <>
      <div className="metric-grid">
        <MetricCard label="Total Active Decisions" value={activeDecisions} hint={latestMeeting ? `Latest: ${latestMeeting.title}` : "No processed meetings yet"} />
        <MetricCard label="Total Superseded" value={appState.decisions.filter((decision) => decision.status === "superseded").length} hint="Archived & documented" />
        <MetricCard label="Pending Resolutions" value={conflictedDecisions || appState.conflicts.length} hint="Requires auditor review" tone="warning" />
        <MetricCard label="Memory Health" value={appState.decisions.length ? "98.2%" : "0%"} hint="Integrity score" tone="success" />
      </div>
      <div className="audit-dashboard-grid">
        <section className="audit-column">
          <div className="panel-header">
            <h3><span className="material-symbols-outlined danger-icon">warning</span> Active Potential Conflicts</h3>
            <span className="badge conflicted">Critical</span>
          </div>
          {conflicts.length ? conflicts.map((decision) => (
            <article className="conflict-ledger-card" key={decision.id}>
              <div className="ledger-card-header">
                <span>ID: {decision.id}</span>
                <strong>DRIFT DETECTED</strong>
              </div>
              <div className="ledger-card-body">
                <small>Contradictory Decision:</small>
                <p className="source-quote danger">{decision.source_excerpt || decision.text}</p>
                <span className="swap-marker material-symbols-outlined">swap_vert</span>
                <small>Existing Grounding:</small>
                <p className="source-quote">{decision.drift?.prior_decision_id || "Prior decision pending review"}</p>
              </div>
            </article>
          )) : (
            <article className="conflict-ledger-card quiet">
              <div className="ledger-card-header">
                <span>ID: HEALTHY</span>
                <strong>NO DRIFT</strong>
              </div>
              <div className="ledger-card-body">
                <p className="source-quote">No unresolved contradictory decisions are currently visible for this team.</p>
              </div>
            </article>
          )}
        </section>
        <section className="panel recent-audits">
          <div className="panel-header">
            <h3>Recent Meeting Audits</h3>
            <div className="inline-actions">
              <button className="secondary-button" type="button"><span className="material-symbols-outlined">filter_list</span> FILTER</button>
              <button className="secondary-button" type="button"><span className="material-symbols-outlined">download</span> EXPORT LEDGER</button>
            </div>
          </div>
          {recentMeetings.length ? (
            <div className="audit-table">
              <div className="audit-table-head">
                <span>Meeting</span><span>Team</span><span>Status</span><span>Trace</span>
              </div>
              {recentMeetings.map((meeting) => (
                <article className="audit-table-row" key={meeting.id}>
                  <strong>{meeting.title}</strong>
                  <span>{meeting.team_id}</span>
                  <span className="badge active">{meeting.status}</span>
                  <small>{meeting.trace_id}</small>
                </article>
              ))}
            </div>
          ) : <ActivityFeed activities={appState.activities} />}
        </section>
      </div>
      <section className="panel dashboard-health">
        <div className="panel-header">
          <h3>Drift Health</h3>
          <span className="muted">New / Related / Potential Conflict</span>
        </div>
        <DriftChart decisions={appState.decisions} />
      </section>
    </>
  );
}
