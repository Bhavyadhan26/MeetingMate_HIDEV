const API = "http://localhost:8000";
const statusEl = document.querySelector("#status");
const decisionsEl = document.querySelector("#decisions");
const answerEl = document.querySelector("#answer");
const briefEl = document.querySelector("#brief-output");

function badge(status) {
  return `<span class="badge ${status}">${status}</span>`;
}

function renderDecision(decision) {
  const drift = decision.drift ? decision.drift.label : "New";
  const prior = decision.drift && decision.drift.prior_decision_id ? `<p>Prior: ${decision.drift.prior_decision_id}</p>` : "";
  const resolve = decision.status === "conflicted" ? `<button data-resolve="${decision.id}" type="button">Resolve</button>` : "";
  return `<article class="decision">
    <div>${badge(decision.status)} ${badge(drift.replaceAll(" ", "-").toLowerCase())}</div>
    <h3>${decision.text}</h3>
    <p>${decision.source_excerpt}</p>
    ${prior}
    ${resolve}
  </article>`;
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
      decisionsEl.innerHTML = result.decisions.map(renderDecision).join("");
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
  answerEl.innerHTML = `<p>${detail.message || "Request failed."}</p>`;
}

document.querySelector("#search").addEventListener("click", async () => {
  const query = encodeURIComponent(document.querySelector("#query").value);
  const team = encodeURIComponent(document.querySelector("#team").value);
  const response = await fetch(`${API}/v1/memory/search?query=${query}&team_id=${team}`);
  const result = await response.json();
  answerEl.innerHTML = `<p>${result.answer}</p>${(result.citations || []).map((item) => `<p><strong>${item.status}</strong> ${item.text}</p>`).join("")}`;
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
    <h3>${topic.topic}</h3>
    <p>${topic.summary}</p>
    ${(topic.citations || []).map((item) => `<p><strong>${item.status}</strong> ${item.text}</p>`).join("")}
  </article>`).join("");
});

decisionsEl.addEventListener("click", async (event) => {
  const id = event.target.getAttribute("data-resolve");
  if (!id) return;
  await fetch(`${API}/v1/decisions/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resolver: "Team Lead", resolver_role: "team_lead", note: "Acknowledged and resolved in demo." })
  });
  event.target.closest(".decision").querySelector(".badge").textContent = "resolved";
  event.target.remove();
});
