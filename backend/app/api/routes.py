from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict
from uuid import uuid4

from backend.app.agents.recall_agent import RecallAgent
from backend.app.memory import get_memory
from backend.app.observability import trace_event
from backend.app.services import MeetingPipeline
from backend.app.services.errors import AppError, AuthorizationError, MalformedTranscriptError, classify_processing_error

memory = get_memory()
pipeline = MeetingPipeline(memory)
recall = RecallAgent(memory)
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = Lock()
_executor = ThreadPoolExecutor(max_workers=int(os.getenv("TRANSCRIPT_JOB_WORKERS", "2")))


def process_transcript(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _process_transcript_payload(payload).model_dump()


def enqueue_transcript(payload: Dict[str, Any]) -> Dict[str, Any]:
    _validate_transcript_payload(payload)
    job_id = f"job-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "job_id": job_id,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
    }
    with _jobs_lock:
        _jobs[job_id] = job
    _executor.submit(_run_transcript_job, job_id, dict(payload))
    return dict(job)


def get_transcript_job(job_id: str) -> Dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return {"error": "Job not found", "job_id": job_id}
        return dict(job)


def _process_transcript_payload(payload: Dict[str, Any]) -> Any:
    transcript = _validate_transcript_payload(payload)
    attendees = _string_list(payload.get("attendees", []), "attendees")
    agenda = _string_list(payload.get("agenda", []), "agenda")
    try:
        return pipeline.process(
            title=str(payload.get("title", "Untitled meeting")),
            team_id=str(payload.get("team_id", "demo-team")),
            transcript_text=transcript,
            attendees=attendees,
            agenda=agenda,
        )
    except Exception as exc:
        raise classify_processing_error(exc, "transcript_ingest") from exc


def _validate_transcript_payload(payload: Dict[str, Any]) -> str:
    transcript = payload.get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        raise MalformedTranscriptError("transcript must be a non-empty string")
    return transcript


def _run_transcript_job(job_id: str, payload: Dict[str, Any]) -> None:
    _update_job(job_id, status="processing", updated_at=datetime.now(timezone.utc).isoformat())
    try:
        result = _process_transcript_payload(payload).model_dump()
        _update_job(job_id, status="completed", result=result, error=None, updated_at=datetime.now(timezone.utc).isoformat())
    except AppError as exc:
        _update_job(job_id, status="failed", result=None, error=exc.to_detail(), updated_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        error = classify_processing_error(exc, "transcript_ingest").to_detail()
        _update_job(job_id, status="failed", result=None, error=error, updated_at=datetime.now(timezone.utc).isoformat())


def _update_job(job_id: str, **fields: Any) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


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
    return resolve_decision_with_role(decision_id, resolver, note, "team_lead")


def resolve_decision_with_role(decision_id: str, resolver: str, note: str, resolver_role: str) -> Dict[str, Any]:
    if resolver_role not in _allowed_resolution_roles():
        raise AuthorizationError(
            "Only team leads, decision owners, or admins can resolve conflicts.",
            detail={"resolver_role": resolver_role, "decision_id": decision_id},
        )
    try:
        updated = memory.update_decision(decision_id, status="resolved", resolved_by=resolver, resolution_note=note)
    except Exception as exc:
        raise classify_processing_error(exc, "decision_resolve") from exc
    if not updated:
        return {"error": "Decision not found", "decision_id": decision_id}
    trace_event("conflict_resolution", "resolved", {"decision_id": decision_id, "resolver": resolver, "resolver_role": resolver_role})
    return {"decision": updated}


def list_unresolved_conflicts(team_id: str = "demo-team") -> Dict[str, Any]:
    try:
        conflicts = memory.list_decisions(team_id=team_id, status="conflicted", limit=100)
    except Exception as exc:
        raise classify_processing_error(exc, "conflict_list") from exc
    timeout_hours = float(os.getenv("CONFLICT_ESCALATION_HOURS", "24"))
    escalated = [_annotate_escalation(decision, timeout_hours) for decision in conflicts]
    for decision in escalated:
        if decision["escalation"]["expired"]:
            trace_event(
                "conflict_resolution",
                "escalated",
                {
                    "decision_id": decision["id"],
                    "team_id": team_id,
                    "age_hours": decision["escalation"]["age_hours"],
                    "timeout_hours": timeout_hours,
                },
            )
    return {"team_id": team_id, "conflicts": escalated, "timeout_hours": timeout_hours}


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


def _allowed_resolution_roles() -> set[str]:
    raw = os.getenv("CONFLICT_RESOLVER_ROLES", "team_lead,decision_owner,admin")
    return {role.strip() for role in raw.split(",") if role.strip()}


def _annotate_escalation(decision: Dict[str, Any], timeout_hours: float) -> Dict[str, Any]:
    created_at = _parse_datetime(decision.get("created_at"))
    age_hours = 0.0
    if created_at is not None:
        age_hours = max(0.0, (datetime.now(timezone.utc) - created_at).total_seconds() / 3600)
    annotated = dict(decision)
    annotated["escalation"] = {
        "expired": age_hours >= timeout_hours,
        "age_hours": round(age_hours, 2),
        "timeout_hours": timeout_hours,
        "behavior": "log conflict_resolution.escalated trace event for reviewer follow-up",
    }
    return annotated


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
