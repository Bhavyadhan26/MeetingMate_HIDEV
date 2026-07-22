const API = window.MEETINGMATE_API_BASE || "http://localhost:8000";
let tokenProvider = null;

export function setAccessTokenProvider(provider) {
  tokenProvider = provider;
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (tokenProvider) {
    const token = await tokenProvider();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }
  const response = await fetch(`${API}${path}`, { ...options, headers });
  const payload = await response.json();
  if (!response.ok) {
    throw payload;
  }
  return payload;
}

export function submitTranscript(payload) {
  return request("/v1/transcripts/async", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function uploadAudio({ file, title, teamId, attendees, agenda }) {
  const form = new FormData();
  form.append("file", file);
  form.append("title", title || "Untitled audio meeting");
  form.append("team_id", teamId || "demo-team");
  form.append("attendees", attendees || "");
  form.append("agenda", agenda || "");
  return request("/v1/transcripts/upload", {
    method: "POST",
    body: form
  });
}

export function getTranscriptJob(jobId) {
  return request(`/v1/transcripts/jobs/${encodeURIComponent(jobId)}`);
}

export function clearQdrantCollections() {
  return request("/v1/admin/qdrant/clear", {
    method: "POST"
  });
}

export function searchMemory(query, teamId) {
  const params = new URLSearchParams({ query, team_id: teamId });
  return request(`/v1/memory/search?${params.toString()}`);
}

export function createPreMeetingBrief(payload) {
  return request("/v1/briefs/pre-meeting", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function listConflicts(teamId) {
  const params = new URLSearchParams({ team_id: teamId });
  return request(`/v1/decisions/conflicts?${params.toString()}`);
}

export function resolveDecisionConflict(decisionId, payload) {
  return request(`/v1/decisions/${encodeURIComponent(decisionId)}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}
