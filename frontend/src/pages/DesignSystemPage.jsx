import { StatusBadge } from "../components/StatusBadge.jsx";

const tokens = [
  ["Primary", "#115e59", "Navigation, primary actions, active state"],
  ["Surface", "#ffffff", "Panels, rows, and modals"],
  ["Canvas", "#f4f6f4", "Application background"],
  ["Conflict", "#b42318", "Risk states and destructive actions"],
  ["Evidence", "#36515f", "Secondary text and audit metadata"]
];

export default function DesignSystemPage() {
  return (
    <>
      <section className="hero-panel compact">
        <div>
          <p className="eyebrow">Design System</p>
          <h3>Minimal auditor UI primitives for MeetingMate.</h3>
          <p>Reusable panels, status chips, tables, controls, and evidence cards are tuned for dense review workflows.</p>
        </div>
        <div className="hero-stack">
          <StatusBadge value="active" />
          <StatusBadge value="conflicted" />
        </div>
      </section>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-header">
            <h3>Color Tokens</h3>
            <span className="muted">Accessible operational palette</span>
          </div>
          <div className="token-list">
            {tokens.map(([name, value, usage]) => (
              <article className="token-row" key={name}>
                <span className="swatch" style={{ background: value }}></span>
                <div>
                  <strong>{name}</strong>
                  <small>{value} | {usage}</small>
                </div>
              </article>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-header">
            <h3>Components</h3>
            <span className="muted">Current production primitives</span>
          </div>
          <div className="component-preview">
            <button type="button">Primary action</button>
            <button className="secondary-button" type="button">Secondary action</button>
            <button className="danger-button" type="button">Danger action</button>
            <div className="inline-actions">
              <StatusBadge value="active" />
              <StatusBadge value="resolved" />
              <StatusBadge value="superseded" />
              <StatusBadge value="conflicted" />
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
