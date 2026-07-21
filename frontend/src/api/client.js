const API = "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, options);
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

export function getTranscriptJob(jobId) {
  return request(`/v1/transcripts/jobs/${encodeURIComponent(jobId)}`);
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
