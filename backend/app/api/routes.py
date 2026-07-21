from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

from backend.app.agents.recall_agent import RecallAgent
from backend.app.memory import get_memory
from backend.app.services import MeetingPipeline
from backend.app.services.errors import MalformedTranscriptError, classify_processing_error

memory = get_memory()
pipeline = MeetingPipeline(memory)
recall = RecallAgent(memory)


def process_transcript(payload: Dict[str, Any]) -> Dict[str, Any]:
    transcript = payload.get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        raise MalformedTranscriptError("transcript must be a non-empty string")
    attendees = _string_list(payload.get("attendees", []), "attendees")
    agenda = _string_list(payload.get("agenda", []), "agenda")
    try:
        result = pipeline.process(
            title=str(payload.get("title", "Untitled meeting")),
            team_id=str(payload.get("team_id", "demo-team")),
            transcript_text=transcript,
            attendees=attendees,
            agenda=agenda,
        )
    except Exception as exc:
        raise classify_processing_error(exc, "transcript_ingest") from exc
    return result.model_dump()


def search_memory(query: str, team_id: str = "demo-team") -> Dict[str, Any]:
    try:
        return recall.answer(query, team_id, trace_id="trace-search")
    except Exception as exc:
        raise classify_processing_error(exc, "memory_search") from exc


def pre_meeting_brief(payload: Dict[str, Any]) -> Dict[str, Any]:
    agenda = payload.get("agenda", [])
    if isinstance(agenda, str):
        agenda = [line.strip() for line in agenda.splitlines() if line.strip()]
    agenda = _string_list(agenda, "agenda")
    if not agenda:
        raise MalformedTranscriptError("agenda must include at least one topic")
    try:
        result = recall.pre_meeting_brief(
            agenda=agenda,
            team_id=str(payload.get("team_id", "demo-team")),
            trace_id=f"trace-brief-{uuid4().hex[:10]}",
        )
    except Exception as exc:
        raise classify_processing_error(exc, "pre_meeting_brief") from exc
    return result.model_dump()


def resolve_decision(decision_id: str, resolver: str, note: str) -> Dict[str, Any]:
    try:
        updated = memory.update_decision(decision_id, status="resolved", resolved_by=resolver, resolution_note=note)
    except Exception as exc:
        raise classify_processing_error(exc, "decision_resolve") from exc
    if not updated:
        return {"error": "Decision not found", "decision_id": decision_id}
    return {"decision": updated}


def _string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise MalformedTranscriptError(f"{field_name} must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise MalformedTranscriptError(f"{field_name} must be a list of strings")
        stripped = item.strip()
        if stripped:
            result.append(stripped)
    return result
