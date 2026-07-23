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
      <section className="settings-header panel">
        <div>
          <h3>Control team scope, privacy posture, and memory reset actions.</h3>
          <p>Redaction maps stay backend-owned; this screen keeps the active team context and guarded Qdrant management workflow visible.</p>
        </div>
        <span className="status">AES-ready metadata store</span>
      </section>
      <section className="panel settings-grid">
        <div>
          <div className="panel-header"><h3>Team Configuration</h3></div>
          <p className="muted">The active team ID is shared across upload, recall, briefs, decisions, and conflicts.</p>
          <label>Active team ID<input onChange={(event) => setTeamId(event.target.value)} value={teamId} /></label>
          <div className="redaction-rule-list">
            {[
              ["person", "Personal Names", "Masking [PERSON_N] identifiers across all transcripts.", true],
              ["contact_mail", "Contact Info", "Emails, phone numbers, and external identifiers.", true],
              ["payments", "Financial Data", "Revenue figures, budgets, and banking credentials.", true],
              ["location_on", "Location Data", "Specific addresses and GPS coordinates.", false]
            ].map(([icon, title, detail, checked]) => (
              <article className="redaction-rule" key={title}>
                <span className="material-symbols-outlined">{icon}</span>
                <div><strong>{title}</strong><small>{detail}</small></div>
                <label className="switch"><input checked={checked} readOnly type="checkbox" /><span></span></label>
              </article>
            ))}
          </div>
        </div>
        <div>
          <div className="panel-header"><h3>Memory Store Management</h3></div>
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
