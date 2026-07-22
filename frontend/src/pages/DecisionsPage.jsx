import { useState } from "react";
import { DecisionCard } from "../components/DecisionCard.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { useDecisions } from "../hooks/useDecisions.js";

export default function DecisionsPage({ appState }) {
  const [filters, setFilters] = useState({ query: "", sort: "newest", status: "all" });
  const decisions = useDecisions(appState.decisions, filters);
  const statuses = ["all", "active", "conflicted", "resolved", "superseded"];

  return (
    <section className="panel">
      <div className="panel-header">
        <h3>Decision Ledger</h3>
        <input className="compact-input" onChange={(event) => setFilters((value) => ({ ...value, query: event.target.value }))} placeholder="Search decisions" value={filters.query} />
      </div>
      <div className="toolbar">
        {statuses.map((status) => (
          <button className={`chip ${filters.status === status ? "active" : ""}`} key={status} onClick={() => setFilters((value) => ({ ...value, status }))} type="button">
            {status[0].toUpperCase() + status.slice(1)}
          </button>
        ))}
        <select className="compact-input" onChange={(event) => setFilters((value) => ({ ...value, sort: event.target.value }))} value={filters.sort}>
          <option value="newest">Newest</option>
          <option value="status">Status</option>
          <option value="drift">Drift label</option>
        </select>
      </div>
      {!decisions.length ? (
        <EmptyState title="No decisions have been extracted yet" message="Upload a meeting to get started." />
      ) : (
        <div className="decision-list">
          {decisions.map((decision) => <DecisionCard decision={decision} key={decision.id} />)}
        </div>
      )}
    </section>
  );
}
