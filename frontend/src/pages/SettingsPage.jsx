import { useState } from "react";
import { ConfirmDialog } from "../components/ConfirmDialog.jsx";
import { ErrorState } from "../components/ErrorState.jsx";
import { useTeam } from "../context/TeamContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { clearQdrantCollections } from "../api/client.js";

export default function SettingsPage({ appState }) {
  const { setTeamId, teamId } = useTeam();
  const { addToast } = useToast();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState(null);

  async function clearCollections() {
    setError(null);
    try {
      await clearQdrantCollections();
      appState.setDecisions([]);
      appState.setConflicts([]);
      appState.addActivity("admin", "Qdrant collections cleared", "decisions, action_items, meeting_chunks");
      addToast("warning", "Collections Cleared", "decisions, action_items, meeting_chunks collections reset");
      setConfirming(false);
    } catch (err) {
      const detail = err?.detail || err || {};
      setError(err);
      addToast("error", "Request Failed", `${detail.message || "Qdrant clear request failed"} (code: ${detail.code || "request_failed"})`);
    }
  }

  return (
    <>
      <section className="panel settings-grid">
        <div>
          <div className="panel-header"><h3>Team Configuration</h3></div>
          <p className="muted">The active team ID is shared across upload, recall, briefs, decisions, and conflicts.</p>
          <label>Active team ID<input onChange={(event) => setTeamId(event.target.value)} value={teamId} /></label>
        </div>
        <div>
          <div className="panel-header"><h3>Qdrant Management</h3></div>
          <p className="muted">This removes MeetingMate vector collections through the backend admin endpoint.</p>
          <button className="danger-button" onClick={() => setConfirming(true)} type="button">Clear All Collections</button>
          {error ? <ErrorState error={error} /> : null}
        </div>
      </section>
      {confirming ? (
        <ConfirmDialog
          confirmLabel="Clear collections"
          message="This deletes the decisions, action_items, and meeting_chunks vector collections."
          onCancel={() => setConfirming(false)}
          onConfirm={clearCollections}
          title="Clear Qdrant collections?"
        />
      ) : null}
    </>
  );
}
