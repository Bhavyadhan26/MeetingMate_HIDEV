"""Run the demo script flow against a live local stack."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

API_BASE = os.getenv("DEMO_API_BASE", "http://localhost:8000")
QDRANT_BASE = os.getenv("DEMO_QDRANT_BASE", "http://localhost:6333")


def main() -> int:
    team_id = os.getenv("DEMO_TEAM_ID", f"demo-{uuid4().hex[:8]}")
    first = process_meeting(
        {
            "title": "Platform architecture kickoff",
            "team_id": team_id,
            "attendees": ["Asha Rao", "Marco Lee"],
            "agenda": ["memory ledger", "ingestion"],
            "transcript": "Asha Rao: We decided use Qdrant as the persistent vector ledger. Marco will prepare the ingestion checklist by Friday.",
        }
    )
    assert first["decisions"], "first meeting did not produce a decision"
    assert first["action_items"], "first meeting did not produce an action item"
    assert "adk parallel extraction" in first["orchestration"], first["orchestration"]

    second = process_meeting(
        {
            "title": "Platform architecture follow-up",
            "team_id": team_id,
            "attendees": ["Asha Rao"],
            "agenda": ["memory ledger"],
            "transcript": "Decision: no longer use Qdrant as the persistent vector ledger.",
        }
    )
    conflicted = [decision for decision in second["decisions"] if decision["status"] == "conflicted"]
    assert conflicted, "second meeting did not produce a conflicted decision"
    conflict_id = conflicted[0]["id"]

    conflicts = request("GET", f"/v1/decisions/conflicts?{urllib.parse.urlencode({'team_id': team_id})}")
    assert any(item["id"] == conflict_id for item in conflicts["conflicts"]), "conflict was not listed"

    resolved = request(
        "POST",
        f"/v1/decisions/{urllib.parse.quote(conflict_id)}/resolve",
        {
            "resolver": "Team Lead",
            "resolver_role": "team_lead",
            "note": "Resolved during demo walkthrough.",
        },
    )
    assert resolved["decision"]["status"] == "resolved", "conflict was not resolved"

    after_resolve = request("GET", f"/v1/decisions/conflicts?{urllib.parse.urlencode({'team_id': team_id})}")
    assert not any(item["id"] == conflict_id for item in after_resolve["conflicts"]), "resolved conflict is still open"

    recall = request("GET", f"/v1/memory/search?{urllib.parse.urlencode({'query': 'What did we decide about Qdrant?', 'team_id': team_id})}")
    assert recall["citations"], "recall did not cite stored decisions"

    brief = request("POST", "/v1/briefs/pre-meeting", {"team_id": team_id, "agenda": ["Qdrant ledger"]})
    assert brief["topics"][0]["citations"], "pre-meeting brief did not cite stored decisions"

    qdrant = request_absolute("GET", f"{QDRANT_BASE}/collections/decisions")
    assert "result" in qdrant, "Qdrant decisions collection was not inspectable"

    print(
        json.dumps(
            {
                "demo_walkthrough": "ok",
                "team_id": team_id,
                "first_decisions": len(first["decisions"]),
                "first_action_items": len(first["action_items"]),
                "conflict_id": conflict_id,
                "resolved_status": resolved["decision"]["status"],
                "recall_citations": len(recall["citations"]),
                "brief_citations": len(brief["topics"][0]["citations"]),
                "qdrant_collection": qdrant["result"]["status"],
                "orchestration": first["orchestration"],
            },
            indent=2,
        )
    )
    return 0


def process_meeting(payload: dict) -> dict:
    job = request("POST", "/v1/transcripts/async", payload)
    job_id = job["job_id"]
    for _ in range(120):
        current = request("GET", f"/v1/transcripts/jobs/{urllib.parse.quote(job_id)}")
        if current["status"] == "completed":
            return current["result"]
        if current["status"] == "failed":
            raise RuntimeError(f"meeting job failed: {current['error']}")
        time.sleep(0.5)
    raise TimeoutError(f"meeting job timed out: {job_id}")


def request(method: str, path: str, payload: dict | None = None) -> dict:
    return request_absolute(method, f"{API_BASE}{path}", payload)


def request_absolute(method: str, url: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_obj = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if payload is not None else {},
    )
    last_error: Exception | None = None
    for _ in range(5):
        try:
            with urllib.request.urlopen(request_obj, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise RuntimeError(f"{method} {url} returned {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"{method} {url} failed after retries: {last_error}")


if __name__ == "__main__":
    raise SystemExit(main())
