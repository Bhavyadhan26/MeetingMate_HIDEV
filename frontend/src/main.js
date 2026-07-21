const API = "http://localhost:8000";
const statusEl = document.querySelector("#status");
const decisionsEl = document.querySelector("#decisions");
const summaryEl = document.querySelector("#summary");
const actionsEl = document.querySelector("#actions");
const answerEl = document.querySelector("#answer");
const briefEl = document.querySelector("#brief-output");
let currentDecisions = [];

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

function renderDecision(decision) {
  const drift = decision.drift ? decision.drift.label : "New";
  const prior = decision.drift && decision.drift.prior_decision_id ? `<p>Prior: ${escapeHtml(decision.drift.prior_decision_id)}</p>` : "";
  const resolve = decision.status === "conflicted" ? `<button data-resolve="${decision.id}" type="button">Resolve</button>` : "";
  return `<article class="decision">
    <div>${badge(decision.status)} ${badge(drift)}</div>
    <h3>${escapeHtml(decision.text)}</h3>
    <p>${escapeHtml(decision.source_excerpt)}</p>
    ${prior}
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

function renderResult(result) {
  renderSummary(result.summary);
  renderActions(result.action_items);
  renderDecisions(result.decisions);
}

document.querySelector("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  statusEl.textContent = "Queued";
  const response = await fetch(`${API}/v1/transcripts/async`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: document.querySelector("#title").value,
      team_id: document.querySelector("#team").value,
      transcript: document.querySelector("#transcript").value,
      attendees: ["Asha Rao", "Marco Lee"],
      agenda: ["memory ledger"]
    })
  });
  const job = await response.json();
  if (!response.ok) {
    showError(job);
    return;
  }
  pollJob(job.job_id);
});

async function pollJob(jobId) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const response = await fetch(`${API}/v1/transcripts/jobs/${jobId}`);
    const job = await response.json();
    if (!response.ok) {
      showError(job);
      return;
    }
    statusEl.textContent = job.status === "processing" ? "Processing" : "Queued";
    if (job.status === "completed") {
      const result = job.result;
      renderResult(result);
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
  const query = encodeURIComponent(document.querySelector("#query").value);
  const team = encodeURIComponent(document.querySelector("#team").value);
  const response = await fetch(`${API}/v1/memory/search?query=${query}&team_id=${team}`);
  const result = await response.json();
  answerEl.innerHTML = `<p>${escapeHtml(result.answer)}</p>${(result.citations || []).map((item) => `<p><strong>${escapeHtml(item.status)}</strong> ${escapeHtml(item.text)}</p>`).join("")}`;
});

document.querySelector("#brief").addEventListener("click", async () => {
  const agenda = document.querySelector("#agenda").value.split(",").map((item) => item.trim()).filter(Boolean);
  const response = await fetch(`${API}/v1/briefs/pre-meeting`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      team_id: document.querySelector("#team").value,
      agenda
    })
  });
  const result = await response.json();
  briefEl.innerHTML = (result.topics || []).map((topic) => `<article class="brief-topic">
    <h3>${escapeHtml(topic.topic)}</h3>
    <p>${escapeHtml(topic.summary)}</p>
    ${(topic.citations || []).map((item) => `<p><strong>${escapeHtml(item.status)}</strong> ${escapeHtml(item.text)}</p>`).join("")}
  </article>`).join("");
});

decisionsEl.addEventListener("click", async (event) => {
  const id = event.target.getAttribute("data-resolve");
  if (!id) return;
  const response = await fetch(`${API}/v1/decisions/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resolver: "Team Lead", resolver_role: "team_lead", note: "Acknowledged and resolved in demo." })
  });
  const result = await response.json();
  if (!response.ok) {
    showError(result);
    return;
  }
  currentDecisions = currentDecisions.map((decision) => decision.id === id ? result.decision : decision);
  renderDecisions(currentDecisions);
});
