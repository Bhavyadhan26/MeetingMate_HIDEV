import React from "react";
import { StatusBadge } from "./StatusBadge.jsx";

function urgencyFor(decision) {
  const hours = Number(decision.escalation?.age_hours || 0);
  if (decision.escalation?.expired || hours >= 24) return { level: "urgent", label: "EXPIRED" };
  if (hours >= 12) return { level: "warning", label: "Due soon" };
  return { level: "normal", label: "Within SLA" };
}

export const ConflictCard = React.memo(function ConflictCard({ conflict, onResolve }) {
  const urgency = urgencyFor(conflict);
  return (
    <article className={`conflict-card ${urgency.level}`}>
      <div className="conflict-topline">
        <StatusBadge value="conflicted" />
        <strong>{urgency.label}</strong>
      </div>
      <h4>{conflict.text}</h4>
      {conflict.source_excerpt ? <p className="quoted">{conflict.source_excerpt}</p> : null}
      {conflict.drift?.prior_decision_id ? <p className="muted">Prior decision: {conflict.drift.prior_decision_id}</p> : null}
      {conflict.escalation ? <p>{conflict.escalation.age_hours}h elapsed of {conflict.escalation.timeout_hours}h SLA</p> : null}
      <button type="button" onClick={() => onResolve(conflict.id)}>Resolve conflict</button>
    </article>
  );
});
