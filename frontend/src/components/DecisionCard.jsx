import React from "react";
import { DriftBadge } from "./DriftBadge.jsx";
import { StatusBadge } from "./StatusBadge.jsx";

function formatDate(value) {
  if (!value) return "Unknown date";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export const DecisionCard = React.memo(function DecisionCard({ decision, onResolve }) {
  const drift = decision.drift?.label || "New";
  const expired = decision.escalation?.expired;
  return (
    <article className="decision">
      <div className="inline-actions">
        <StatusBadge value={decision.status} />
        <DriftBadge value={drift} />
        {expired ? <StatusBadge value="Potential Conflict" /> : null}
      </div>
      <h4>{decision.text}</h4>
      {decision.source_excerpt ? <p className="quoted">{decision.source_excerpt}</p> : null}
      <small>{decision.meeting_title || decision.meeting_id || "Meeting"} | {formatDate(decision.created_at)}</small>
      {decision.drift?.prior_decision_id ? <p className="muted">Prior decision: {decision.drift.prior_decision_id}</p> : null}
      {decision.superseded_by ? <p className="muted">Superseded by: {decision.superseded_by}</p> : null}
      {decision.escalation ? (
        <p className={expired ? "conflicted badge" : "status"}>
          {expired ? "Escalation expired" : "Within SLA"} | {decision.escalation.age_hours}h
        </p>
      ) : null}
      {decision.status === "conflicted" && onResolve ? (
        <button type="button" onClick={() => onResolve(decision.id)}>Resolve</button>
      ) : null}
    </article>
  );
});
