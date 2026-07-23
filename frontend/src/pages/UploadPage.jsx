import { useEffect, useMemo, useRef, useState } from "react";
import { ActionItemCard } from "../components/ActionItemCard.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { ErrorState } from "../components/ErrorState.jsx";
import { LoadingSpinner } from "../components/LoadingSpinner.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";
import { useTeam } from "../context/TeamContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { submitTranscript, uploadAudio } from "../api/client.js";
import { useTranscriptJob } from "../hooks/useAsyncJob.js";

const defaultTranscript = "Asha Rao: We decided use Qdrant as the persistent vector ledger. Marco will prepare the ingestion checklist by Friday.";

function parseList(value) {
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function apiErrorMessage(error, fallback) {
  const detail = error?.detail || error || {};
  return {
    code: detail.code || "request_failed",
    message: detail.message || fallback
  };
}

function PipelinePanel({ jobId, jobState, onClose, pipelineError, submitting }) {
  if (!jobId && !submitting && !pipelineError) return null;
  const failed = Boolean(pipelineError || jobState.error || jobState.job?.status === "failed");
  const activeLabel = pipelineError ? "Request failed" : submitting ? "Queueing meeting" : jobState.steps[jobState.activeStep] || "Preparing";
  const progress = pipelineError ? 100 : submitting ? 8 : jobState.progress;
  const status = pipelineError ? "failed" : submitting ? "queued" : jobState.job?.status || "queued";
  return (
    <div className="pipeline-modal-backdrop" role="status" aria-live="polite">
      <section className="pipeline-modal" aria-label="Agent pipeline processing status">
        <div className="pipeline-orb" aria-hidden="true">
          <span></span>
        </div>
        <div className="pipeline-modal-header">
          <div>
            <p className="eyebrow">Agent Pipeline</p>
            <h3>{activeLabel}</h3>
            <p>MeetingMate agents are redacting, extracting, checking drift, and writing memory.</p>
          </div>
          <div className="pipeline-progress-number">{Math.round(jobState.progress)}%</div>
        </div>
        <div className="inline-actions">
          <StatusBadge value={status} />
          <span className="status">{jobId || "Creating job"}</span>
          {failed ? <StatusBadge value="failed" /> : null}
        </div>
        <div className="progress-shell elevated">
          <div className={`progress-bar ${failed ? "failed" : ""}`} style={{ width: `${progress}%` }}></div>
        </div>
        {pipelineError ? <div className="error-state"><strong>{pipelineError.code}</strong><p>{pipelineError.message}</p></div> : null}
        <div className="pipeline-steps">
          {jobState.steps.map((step, index) => {
            let status = "pending";
            if (failed && index === jobState.activeStep) status = "failed";
            else if (index < jobState.activeStep) status = "done";
            else if (index === jobState.activeStep) status = "running";
            if (submitting) status = index === 0 ? "running" : "pending";
            return (
              <article className={`pipeline-step ${status}`} key={step}>
                <span className="step-indicator"></span>
                <div>
                  <strong>{step}</strong>
                  <small>{status}</small>
                </div>
              </article>
            );
          })}
        </div>
        <div className="pipeline-footer">
          <p className="pipeline-footnote">{failed ? "Fix the request issue and try again." : "This window closes automatically when processing finishes."}</p>
          {failed ? <button className="secondary-button" onClick={onClose} type="button">Close</button> : null}
        </div>
      </section>
    </div>
  );
}

function PipelinePreview() {
  const steps = ["Transcribing", "Redacting", "Extracting", "Detecting Drift", "Persisting"];
  return (
    <section className="panel pipeline-preview">
      <div className="panel-header">
        <h3>Agent Pipeline</h3>
        <span className="muted">Appears after processing starts</span>
      </div>
      <div className="pipeline-preview-grid">
        {steps.map((step) => <span key={step}>{step}</span>)}
      </div>
      <p className="muted">Click Process Text or Upload Audio to open the live pipeline overlay.</p>
    </section>
  );
}

export default function UploadPage({ appState }) {
  const { setTeamId, teamId } = useTeam();
  const { addToast } = useToast();
  const [agenda, setAgenda] = useState("memory ledger, ingestion");
  const [attendees, setAttendees] = useState("Asha Rao, Marco Lee");
  const [audioFile, setAudioFile] = useState(null);
  const [error, setError] = useState(null);
  const [jobId, setJobId] = useState("");
  const [pipelineError, setPipelineError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [summary, setSummary] = useState(null);
  const [title, setTitle] = useState("Platform architecture sync");
  const [transcript, setTranscript] = useState(defaultTranscript);
  const jobState = useTranscriptJob(jobId);
  const lastStatusRef = useRef("");

  useEffect(() => {
    const status = jobState.job?.status;
    if (!status || status === lastStatusRef.current) return;
    lastStatusRef.current = status;

    if (status === "processing") {
      appState.setStatus("Processing");
      addToast("info", "Processing", "AI agents are extracting decisions and detecting drift...");
    }

    if (status === "completed" && jobState.job.result) {
      appState.setStatus(`Trace ${jobState.job.result.trace_id}`);
      appState.addMeetingResult(jobState.job.result, { title, team_id: teamId });
      setSummary(jobState.job.result.summary);
      setPipelineError(null);
      addToast(
        "success",
        "Meeting Processed",
        `${jobState.job.result.decisions?.length || 0} decisions, ${jobState.job.result.action_items?.length || 0} action items extracted`
      );
      setJobId("");
    }
    if (status === "failed") {
      const detail = apiErrorMessage(jobState.job.error, "Transcript job failed");
      appState.setStatus("Failed");
      addToast("error", "Processing Failed", `Error: ${detail.code} - ${detail.message}`);
    }
  }, [addToast, appState, jobState.job, teamId, title]);

  const canUploadAudio = useMemo(() => Boolean(audioFile), [audioFile]);

  async function processText(event) {
    event.preventDefault();
    setError(null);
    setPipelineError(null);
    setSubmitting(true);
    appState.setStatus("Queued");
    try {
      const job = await submitTranscript({
        agenda: parseList(agenda),
        attendees: parseList(attendees),
        team_id: teamId,
        title,
        transcript
      });
      setJobId(job.job_id);
      setSubmitting(false);
      lastStatusRef.current = "";
      addToast("info", "Job Queued", `Meeting transcript queued for processing (${job.job_id})`);
    } catch (err) {
      const detail = apiErrorMessage(err, "Transcript request failed");
      setError(err);
      setPipelineError(detail);
      setSubmitting(false);
      appState.setStatus("Error");
      addToast("error", "Request Failed", `${detail.message} (code: ${detail.code})`);
    }
  }

  async function processAudio() {
    if (!audioFile) return;
    setError(null);
    setPipelineError(null);
    setSubmitting(true);
    appState.setStatus("Audio queued");
    try {
      const job = await uploadAudio({ file: audioFile, title, teamId, attendees, agenda });
      setJobId(job.job_id);
      setSubmitting(false);
      lastStatusRef.current = "";
      addToast("info", "Job Queued", `Audio upload queued for processing (${job.job_id})`);
    } catch (err) {
      const detail = apiErrorMessage(err, "Audio request failed");
      setError(err);
      setPipelineError(detail);
      setSubmitting(false);
      appState.setStatus("Error");
      addToast("error", "Request Failed", `${detail.message} (code: ${detail.code})`);
    }
  }

  function onDrop(event) {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (file) setAudioFile(file);
  }

  return (
    <>
      <section className="hero-panel compact">
        <div>
          <p className="eyebrow">AI Meeting Intelligence PRD</p>
          <h3>Ingest transcripts or audio and audit the resulting meeting memory.</h3>
          <p>Existing text input, Deepgram audio upload, extraction, drift detection, and Qdrant persistence remain wired to the same backend workflow.</p>
        </div>
        <div className="spec-list">
          <span>PII redaction</span>
          <span>Summary</span>
          <span>Actions</span>
          <span>Decision drift</span>
        </div>
      </section>
      <div className="workspace">
        <form className="panel" onSubmit={processText}>
          <div className="panel-header">
            <h3>Meeting Intake</h3>
            <span className="muted">Transcript or diarized audio</span>
          </div>
          <div className="form-grid">
            <label>Title<input onChange={(event) => setTitle(event.target.value)} value={title} /></label>
            <label>Team ID<input onChange={(event) => setTeamId(event.target.value)} value={teamId} /></label>
            <label>Attendees<input onChange={(event) => setAttendees(event.target.value)} value={attendees} /></label>
            <label>Agenda<input onChange={(event) => setAgenda(event.target.value)} value={agenda} /></label>
          </div>
          <label>Transcript<textarea onChange={(event) => setTranscript(event.target.value)} value={transcript} /></label>
          <label className="drop-zone" onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
            <span>{audioFile ? audioFile.name : "Drop audio here or choose a file"}</span>
            <input accept=".mp3,.wav,.m4a,.ogg,audio/*" onChange={(event) => setAudioFile(event.target.files?.[0] || null)} type="file" />
            <button className="secondary-button" type="button" onClick={(event) => event.currentTarget.parentElement.querySelector("input").click()}>Choose File</button>
          </label>
          <div className="upload-actions">
            <button disabled={jobId} type="submit">Process Text</button>
            <button disabled={!canUploadAudio || jobId} onClick={processAudio} type="button">Upload Audio</button>
          </div>
          {error ? <ErrorState error={error} /> : null}
        </form>
        <PipelinePreview />
      </div>
      <PipelinePanel
        jobId={jobId}
        jobState={jobState}
        onClose={() => {
          setPipelineError(null);
          if (jobState.job?.status === "failed") setJobId("");
        }}
        pipelineError={pipelineError}
        submitting={submitting}
      />

      <div className="results-grid">
        <section className="panel">
          <div className="panel-header"><h3>Executive Summary</h3></div>
          {jobId && !summary ? <LoadingSpinner label="Waiting for summary" /> : summary ? (
            <div className="answer">
              <p>{summary.tldr}</p>
              <ul>{(summary.key_points || []).map((point) => <li key={point}>{point}</li>)}</ul>
            </div>
          ) : <EmptyState title="No summary yet" message="Process a meeting to generate a concise summary." />}
        </section>
        <section className="panel">
          <div className="panel-header"><h3>Accountability Log</h3></div>
          {appState.actions.length ? (
            <div className="action-list">{appState.actions.map((item, index) => <ActionItemCard item={item} key={`${item.task}-${index}`} />)}</div>
          ) : <EmptyState title="No action items yet" message="Action items will appear after extraction completes." />}
        </section>
      </div>
    </>
  );
}
