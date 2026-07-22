import {
  createPreMeetingBrief,
  clearQdrantCollections,
  getTranscriptJob,
  listConflicts,
  resolveDecisionConflict,
  searchMemory,
  setAccessTokenProvider,
  submitTranscript,
  uploadAudio
} from "./api/client.js";

const statusEl = document.querySelector("#status");
const decisionsEl = document.querySelector("#decisions");
const conflictsEl = document.querySelector("#conflicts");
const conflictCountEl = document.querySelector("#conflict-count");
const summaryEl = document.querySelector("#summary");
const actionsEl = document.querySelector("#actions");
const answerEl = document.querySelector("#answer");
const briefEl = document.querySelector("#brief-output");
const loginEl = document.querySelector("#login");
const logoutEl = document.querySelector("#logout");
const userEl = document.querySelector("#user");
let currentDecisions = [];
let currentConflicts = [];
let auth0Client = null;

function badge(status) {
  const value = String(status || "unknown");
  return `<span class="badge ${cssToken(value)}">${escapeHtml(value)}</span>`;
}

function cssToken(value) {
  return String(value || "unknown").replaceAll(" ", "-").toLowerCase();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;"
  }[char]));
}

function parseList(value) {
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

async function initAuth() {
  const backendConfig = await fetchAuthConfig();
  const domain = backendConfig.domain || window.MEETINGMATE_AUTH0_DOMAIN;
  const clientId = backendConfig.client_id || window.MEETINGMATE_AUTH0_CLIENT_ID;
  const audience = backendConfig.audience || window.MEETINGMATE_AUTH0_AUDIENCE;
  if (!domain || !clientId || !window.auth0) {
    userEl.textContent = "Auth optional";
    return;
  }
  auth0Client = await window.auth0.createAuth0Client({
    domain,
    clientId,
    authorizationParams: {
      audience,
      redirect_uri: window.location.origin + window.location.pathname
    }
  });
  if (window.location.search.includes("code=") && window.location.search.includes("state=")) {
    await auth0Client.handleRedirectCallback();
    window.history.replaceState({}, document.title, window.location.pathname);
  }
  const authenticated = await auth0Client.isAuthenticated();
  loginEl.hidden = authenticated;
  logoutEl.hidden = !authenticated;
  if (authenticated) {
    const user = await auth0Client.getUser();
    userEl.textContent = user.email || user.name || "Signed in";
    setAccessTokenProvider(() => auth0Client.getTokenSilently());
  } else {
    userEl.textContent = "Signed out";
  }
}

async function fetchAuthConfig() {
  try {
    const response = await fetch(`${window.MEETINGMATE_API_BASE || "http://localhost:8000"}/v1/auth/config`);
    if (!response.ok) return {};
    return response.json();
  } catch {
    return {};
  }
}

loginEl.addEventListener("click", async () => {
  if (!auth0Client) return;
  await auth0Client.loginWithRedirect();
});

logoutEl.addEventListener("click", () => {
  if (!auth0Client) return;
  auth0Client.logout({ logoutParams: { returnTo: window.location.origin + window.location.pathname } });
});

function renderDecision(decision) {
  const drift = decision.drift ? decision.drift.label : "New";
  const prior = decision.drift && decision.drift.prior_decision_id ? `<p>Prior: ${escapeHtml(decision.drift.prior_decision_id)}</p>` : "";
  const escalation = decision.escalation ? `<p><strong>Escalation</strong> ${decision.escalation.expired ? "expired" : "within SLA"} (${escapeHtml(decision.escalation.age_hours)}h / ${escapeHtml(decision.escalation.timeout_hours)}h)</p>` : "";
  const resolve = decision.status === "conflicted" ? `<button data-resolve="${escapeHtml(decision.id)}" type="button">Resolve</button>` : "";
  return `<article class="decision">
    <div>${badge(decision.status)} ${badge(drift)}</div>
    <h3>${escapeHtml(decision.text)}</h3>
    <p>${escapeHtml(decision.source_excerpt)}</p>
    ${prior}
    ${escalation}
    ${resolve}
  </article>`;
}

function renderSummary(summary) {
  if (!summary) {
    summaryEl.classList.add("empty-state");
    summaryEl.textContent = "No summary yet.";
    return;
  }
  summaryEl.classList.remove("empty-state");
  summaryEl.innerHTML = `<p>${escapeHtml(summary.tldr)}</p><ul>${(summary.key_points || []).map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>`;
}

function renderActions(actions) {
  if (!actions || actions.length === 0) {
    actionsEl.classList.add("empty-state");
    actionsEl.textContent = "No action items found.";
    return;
  }
  actionsEl.classList.remove("empty-state");
  actionsEl.innerHTML = actions.map((item) => `<article class="action-item">
    <h3>${escapeHtml(item.task)}</h3>
    <p><strong>Owner</strong> ${escapeHtml(item.owner || "Unassigned")}</p>
    ${item.deadline ? `<p><strong>Deadline</strong> ${escapeHtml(item.deadline)}</p>` : ""}
    <p>${escapeHtml(item.source_excerpt)}</p>
  </article>`).join("");
}

function renderDecisions(decisions) {
  currentDecisions = decisions || [];
  if (currentDecisions.length === 0) {
    decisionsEl.classList.add("empty-state");
    decisionsEl.textContent = "No decisions found.";
    return;
  }
  decisionsEl.classList.remove("empty-state");
  decisionsEl.innerHTML = currentDecisions.map(renderDecision).join("");
}

function renderConflicts(conflicts) {
  currentConflicts = conflicts || [];
  conflictCountEl.textContent = `${currentConflicts.length} open`;
  if (currentConflicts.length === 0) {
    conflictsEl.classList.add("empty-state");
    conflictsEl.textContent = "No unresolved conflicts.";
    return;
  }
  conflictsEl.classList.remove("empty-state");
  conflictsEl.innerHTML = currentConflicts.map(renderDecision).join("");
}

function renderResult(result) {
  renderSummary(result.summary);
  renderActions(result.action_items);
  renderDecisions(result.decisions);
}

document.querySelector("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  statusEl.textContent = "Queued";
  try {
    const job = await submitTranscript({
      title: document.querySelector("#title").value,
      team_id: document.querySelector("#team").value,
      transcript: document.querySelector("#transcript").value,
      attendees: parseList(document.querySelector("#attendees").value),
      agenda: parseList(document.querySelector("#upload-agenda").value)
    });
    pollJob(job.job_id);
  } catch (error) {
    showError(error);
  }
});

document.querySelector("#audio-upload").addEventListener("click", async () => {
  const file = document.querySelector("#audio-file").files[0];
  if (!file) {
    statusEl.textContent = "Choose audio";
    return;
  }
  statusEl.textContent = "Audio queued";
  try {
    const job = await uploadAudio({
      file,
      title: document.querySelector("#title").value,
      teamId: document.querySelector("#team").value,
      attendees: document.querySelector("#attendees").value,
      agenda: document.querySelector("#upload-agenda").value
    });
    pollJob(job.job_id);
  } catch (error) {
    showError(error);
  }
});

async function pollJob(jobId) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    let job;
    try {
      job = await getTranscriptJob(jobId);
    } catch (error) {
      showError(error);
      return;
    }
    statusEl.textContent = job.status === "processing" ? "Processing" : "Queued";
    if (job.status === "completed") {
      const result = job.result;
      renderResult(result);
      await refreshConflicts();
      statusEl.textContent = `Trace ${result.trace_id}`;
      return;
    }
    if (job.status === "failed") {
      showError(job.error);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  statusEl.textContent = "Timed out";
}

function showError(error) {
  const detail = error.detail || error;
  statusEl.textContent = detail.code || "Error";
  answerEl.innerHTML = `<p>${escapeHtml(detail.message || "Request failed.")}</p>`;
}

document.querySelector("#search").addEventListener("click", async () => {
  try {
    const result = await searchMemory(document.querySelector("#query").value, document.querySelector("#team").value);
    answerEl.innerHTML = `<p>${escapeHtml(result.answer)}</p>${(result.citations || []).map((item) => `<p><strong>${escapeHtml(item.status)}</strong> ${escapeHtml(item.text)}</p>`).join("")}`;
  } catch (error) {
    showError(error);
  }
});

document.querySelector("#brief").addEventListener("click", async () => {
  const agenda = document.querySelector("#agenda").value.split(",").map((item) => item.trim()).filter(Boolean);
  try {
    const result = await createPreMeetingBrief({
      team_id: document.querySelector("#team").value,
      agenda
    });
    briefEl.innerHTML = (result.topics || []).map((topic) => `<article class="brief-topic">
      <h3>${escapeHtml(topic.topic)}</h3>
      <p>${escapeHtml(topic.summary)}</p>
      ${(topic.citations || []).map((item) => `<p><strong>${escapeHtml(item.status)}</strong> ${escapeHtml(item.text)}</p>`).join("")}
    </article>`).join("");
  } catch (error) {
    showError(error);
  }
});

document.querySelector("#refresh-conflicts").addEventListener("click", refreshConflicts);
document.querySelector("#clear-qdrant").addEventListener("click", async () => {
  statusEl.textContent = "Clearing Qdrant";
  try {
    await clearQdrantCollections();
    currentDecisions = [];
    currentConflicts = [];
    renderDecisions([]);
    renderConflicts([]);
    answerEl.textContent = "";
    briefEl.textContent = "";
    statusEl.textContent = "Qdrant cleared";
  } catch (error) {
    showError(error);
  }
});

async function refreshConflicts() {
  let result;
  try {
    result = await listConflicts(document.querySelector("#team").value);
  } catch (error) {
    showError(error);
    return;
  }
  renderConflicts(result.conflicts || []);
}

async function resolveDecision(id) {
  let result;
  try {
    result = await resolveDecisionConflict(id, {
      resolver: document.querySelector("#resolver").value || "Reviewer",
      resolver_role: document.querySelector("#resolver-role").value,
      note: document.querySelector("#resolution-note").value || "Resolved in review."
    });
  } catch (error) {
    showError(error);
    return;
  }
  currentDecisions = currentDecisions.map((decision) => decision.id === id ? result.decision : decision);
  currentConflicts = currentConflicts.filter((decision) => decision.id !== id);
  renderDecisions(currentDecisions);
  renderConflicts(currentConflicts);
}

function handleResolveClick(event) {
  const id = event.target.getAttribute("data-resolve");
  if (!id) return;
  resolveDecision(id);
}

decisionsEl.addEventListener("click", handleResolveClick);
conflictsEl.addEventListener("click", handleResolveClick);

initAuth().catch(showError);
