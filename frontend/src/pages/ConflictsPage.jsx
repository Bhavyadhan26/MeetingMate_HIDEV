import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ConflictCard } from "../components/ConflictCard.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { ErrorState } from "../components/ErrorState.jsx";
import { LoadingSpinner } from "../components/LoadingSpinner.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";
import { useTeam } from "../context/TeamContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { resolveDecisionConflict } from "../api/client.js";
import { useConflicts } from "../hooks/useConflicts.js";

export default function ConflictsPage({ appState }) {
  const { teamId } = useTeam();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const { conflicts, error, loading, refresh, setConflicts } = useConflicts(teamId);
  const [resolver, setResolver] = useState("Team Lead");
  const [resolverRole, setResolverRole] = useState("team_lead");
  const [note, setNote] = useState("Acknowledged and resolved in review.");
  const flaggedRef = useRef(new Set());
  const notifiedRef = useRef(new Set());

  useEffect(() => {
    appState.setConflicts(conflicts);
    const newConflicts = conflicts.filter((conflict) => !flaggedRef.current.has(conflict.id));
    newConflicts.forEach((conflict) => flaggedRef.current.add(conflict.id));
    if (newConflicts.length) {
      addToast("warning", "Conflict Flagged", "New decision contradicts prior active decision");
    }
    conflicts.forEach((conflict) => {
      if (!conflict.escalation?.expired || notifiedRef.current.has(conflict.id)) return;
      notifiedRef.current.add(conflict.id);
      addToast(
        "conflict",
        "Escalation Notice",
        `Conflict '${conflict.text}' has exceeded ${conflict.escalation.timeout_hours}h timeout. Team Lead has been notified.`,
        {
          action: { label: "View Conflict", onClick: () => navigate("/conflicts") },
          persistent: true
        }
      );
    });
  }, [addToast, appState, conflicts, navigate]);

  async function resolve(id) {
    try {
      const result = await resolveDecisionConflict(id, { note, resolver, resolver_role: resolverRole });
      setConflicts((items) => items.filter((item) => item.id !== id));
      appState.replaceDecision(result.decision);
      appState.addActivity("resolved", "Decision conflict resolved", id);
      addToast("success", "Conflict Resolved", `Decision marked as resolved by ${resolver}`);
    } catch (err) {
      const detail = err?.detail || err || {};
      addToast("error", "Request Failed", `${detail.message || "Decision could not be resolved"} (code: ${detail.code || "request_failed"})`);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h3>Conflict Audit Center</h3>
        <div className="inline-actions">
          <button onClick={() => refresh().catch(() => {})} type="button">Refresh</button>
          <StatusBadge value={`${conflicts.length} open`} />
          <span className="muted">24h escalation timeout</span>
        </div>
      </div>
      <div className="review-row">
        <input onChange={(event) => setResolver(event.target.value)} value={resolver} />
        <select onChange={(event) => setResolverRole(event.target.value)} value={resolverRole}>
          <option value="team_lead">team_lead</option>
          <option value="decision_owner">decision_owner</option>
          <option value="admin">admin</option>
          <option value="observer">observer</option>
        </select>
        <input onChange={(event) => setNote(event.target.value)} value={note} />
      </div>
      {loading ? <LoadingSpinner label="Loading conflicts" /> : null}
      {error ? <ErrorState error={error} onRetry={() => refresh().catch(() => {})} /> : null}
      {!loading && !error && !conflicts.length ? (
        <EmptyState title="No unresolved conflicts" message="Your decision ledger is healthy." />
      ) : (
        <div className="conflict-grid">
          {conflicts.map((conflict) => <ConflictCard conflict={conflict} key={conflict.id} onResolve={resolve} />)}
        </div>
      )}
    </section>
  );
}
