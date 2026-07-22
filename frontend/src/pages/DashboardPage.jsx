import { ActivityFeed } from "../components/ActivityFeed.jsx";
import { DriftChart } from "../components/DriftChart.jsx";
import { MetricCard } from "../components/MetricCard.jsx";

export default function DashboardPage({ appState }) {
  const activeDecisions = appState.decisions.filter((decision) => decision.status === "active").length;
  return (
    <>
      <div className="metric-grid">
        <MetricCard label="Meetings" value={appState.meetings.length} hint={appState.meetings.length ? "Processed in this browser" : "No processed meetings yet"} />
        <MetricCard label="Active Decisions" value={activeDecisions} hint="Stored in the decision ledger" />
        <MetricCard label="Open Conflicts" value={appState.conflicts.length} hint={appState.conflicts.length ? "Review required" : "Decision ledger is healthy"} tone={appState.conflicts.length ? "conflicted" : ""} />
        <MetricCard label="Action Items" value={appState.actions.length} hint="From the latest processed meeting" />
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-header">
            <h3>Drift Health</h3>
            <span className="muted">New / Related / Potential Conflict</span>
          </div>
          <DriftChart decisions={appState.decisions} />
        </section>
        <section className="panel">
          <div className="panel-header">
            <h3>Recent Activity</h3>
            <span className="muted">Latest session events</span>
          </div>
          <ActivityFeed activities={appState.activities} />
        </section>
      </div>
    </>
  );
}
