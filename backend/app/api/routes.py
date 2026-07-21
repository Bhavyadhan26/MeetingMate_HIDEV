from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

from backend.app.agents.recall_agent import RecallAgent
from backend.app.memory import get_memory
from backend.app.services import MeetingPipeline

memory = get_memory()
pipeline = MeetingPipeline(memory)
recall = RecallAgent(memory)


def process_transcript(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = pipeline.process(
        title=payload.get("title", "Untitled meeting"),
        team_id=payload.get("team_id", "demo-team"),
        transcript_text=payload["transcript"],
        attendees=payload.get("attendees", []),
        agenda=payload.get("agenda", []),
    )
    return result.model_dump()


def search_memory(query: str, team_id: str = "demo-team") -> Dict[str, Any]:
    return recall.answer(query, team_id, trace_id="trace-search")


def pre_meeting_brief(payload: Dict[str, Any]) -> Dict[str, Any]:
    agenda = payload.get("agenda", [])
    if isinstance(agenda, str):
        agenda = [line.strip() for line in agenda.splitlines() if line.strip()]
    result = recall.pre_meeting_brief(
        agenda=agenda,
        team_id=payload.get("team_id", "demo-team"),
        trace_id=f"trace-brief-{uuid4().hex[:10]}",
    )
    return result.model_dump()


def resolve_decision(decision_id: str, resolver: str, note: str) -> Dict[str, Any]:
    updated = memory.update_decision(decision_id, status="resolved", resolved_by=resolver, resolution_note=note)
    if not updated:
        return {"error": "Decision not found", "decision_id": decision_id}
    return {"decision": updated}
