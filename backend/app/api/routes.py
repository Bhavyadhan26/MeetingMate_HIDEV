from __future__ import annotations

import os
import shutil
import time as _time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional
from uuid import uuid4

from backend.app.agents.recall_agent import RecallAgent
from backend.app.memory import get_memory
from backend.app.memory.vector_store import VectorMemory
from backend.app.observability import trace_event
from backend.app.services.deepgram import transcribe_audio_file
from backend.app.services import MeetingPipeline
from backend.app.services.errors import AppError, DependencyUnavailableError, AuthorizationError, MalformedTranscriptError, classify_processing_error

_memory: Optional[VectorMemory] = None
_pipeline: Optional[MeetingPipeline] = None
_recall: Optional[RecallAgent] = None
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = Lock()
_executor = ThreadPoolExecutor(max_workers=int(os.getenv("TRANSCRIPT_JOB_WORKERS", "2")))
_TERMINAL_JOB_STATUSES = {"completed", "failed"}
_AUDIO_UPLOAD_ROOT = Path(os.getenv("AUDIO_UPLOAD_ROOT", "backend/audio_uploads"))
_ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg"}


def _ensure_initialized() -> None:
    global _memory, _pipeline, _recall
    if _memory is not None:
        return
    last_error: Optional[Exception] = None
    for attempt in range(20):
        try:
            _memory = get_memory()
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            if attempt < 19:
                _time.sleep(1.5)
    if last_error is not None:
        _memory = None
        raise DependencyUnavailableError(
            "Memory backend (Qdrant) is unavailable after 30 seconds. Retry after the service is healthy.",
            detail={"error": str(last_error)},
        ) from last_error
    _pipeline = MeetingPipeline(_memory)
    _recall = RecallAgent(_memory)


def process_transcript(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _process_transcript_payload(payload).model_dump()


def enqueue_transcript(payload: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_initialized()
    _validate_transcript_payload(payload)
    job_id = f"job-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "job_id": job_id,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "expires_at": None,
        "result": None,
        "error": None,
    }
    with _jobs_lock:
        _purge_expired_jobs_locked()
        _jobs[job_id] = job
    _executor.submit(_run_transcript_job, job_id, dict(payload))
    return dict(job)


def enqueue_audio_transcript(
    *,
    filename: str,
    content: bytes,
    content_type: str | None,
    title: str = "Untitled audio meeting",
    team_id: str = "demo-team",
    attendees: list[str] | None = None,
    agenda: list[str] | None = None,
) -> Dict[str, Any]:
    _ensure_initialized()
    if not content:
        raise MalformedTranscriptError("audio file must not be empty")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in _ALLOWED_AUDIO_EXTENSIONS:
        raise MalformedTranscriptError("audio file must be one of: mp3, wav, m4a, ogg")
    job_id = f"job-{uuid4().hex[:12]}"
    job_dir = _AUDIO_UPLOAD_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    audio_path = job_dir / f"upload{suffix}"
    audio_path.write_bytes(content)
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "job_id": job_id,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "expires_at": None,
        "result": None,
        "error": None,
    }
    with _jobs_lock:
        _purge_expired_jobs_locked()
        _jobs[job_id] = job
    _executor.submit(
        _run_audio_transcript_job,
        job_id,
        audio_path,
        content_type,
        {
            "title": title,
            "team_id": team_id,
            "attendees": attendees or [],
            "agenda": agenda or [],
        },
    )
    return dict(job)


def get_transcript_job(job_id: str) -> Dict[str, Any]:
    with _jobs_lock:
        _purge_expired_jobs_locked()
        job = _jobs.get(job_id)
        if not job:
            return {"error": "Job not found", "job_id": job_id}
        return dict(job)


def _process_transcript_payload(payload: Dict[str, Any]) -> Any:
    _ensure_initialized()
    transcript = _validate_transcript_payload(payload)
    attendees = _string_list(payload.get("attendees", []), "attendees")
    agenda = _string_list(payload.get("agenda", []), "agenda")
    try:
        return _pipeline.process(
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
        _finish_job(job_id, status="completed", result=result, error=None)
    except AppError as exc:
        _finish_job(job_id, status="failed", result=None, error=exc.to_detail())
    except Exception as exc:
        error = classify_processing_error(exc, "transcript_ingest").to_detail()
        _finish_job(job_id, status="failed", result=None, error=error)


def _run_audio_transcript_job(job_id: str, audio_path: Path, content_type: str | None, payload: Dict[str, Any]) -> None:
    _update_job(job_id, status="processing", updated_at=datetime.now(timezone.utc).isoformat())
    try:
        transcript = transcribe_audio_file(audio_path, content_type)
        result = _process_transcript_payload({**payload, "transcript": transcript}).model_dump()
        result["audio_transcription"] = {"provider": "deepgram", "speaker_tagged": True}
        _finish_job(job_id, status="completed", result=result, error=None)
    except AppError as exc:
        _finish_job(job_id, status="failed", result=None, error=exc.to_detail())
    except Exception as exc:
        error = classify_processing_error(exc, "audio_transcript_upload").to_detail()
        _finish_job(job_id, status="failed", result=None, error=error)
    finally:
        shutil.rmtree(audio_path.parent, ignore_errors=True)


def _finish_job(job_id: str, status: str, result: Any, error: Any) -> None:
    now = datetime.now(timezone.utc)
    _update_job(
        job_id,
        status=status,
        result=result,
        error=error,
        updated_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=_job_ttl_seconds())).isoformat(),
    )


def _update_job(job_id: str, **fields: Any) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def _job_ttl_seconds() -> int:
    try:
        ttl_seconds = int(os.getenv("TRANSCRIPT_JOB_TTL_SECONDS", "3600"))
    except ValueError:
        ttl_seconds = 3600
    return max(1, ttl_seconds)


def _purge_expired_jobs_locked(now: datetime | None = None) -> None:
    current = now or datetime.now(timezone.utc)
    expired_ids: list[str] = []
    for job_id, job in _jobs.items():
        if job.get("status") not in _TERMINAL_JOB_STATUSES:
            continue
        expires_at = _parse_datetime(job.get("expires_at"))
        if expires_at is not None and expires_at <= current:
            expired_ids.append(job_id)
    for job_id in expired_ids:
        del _jobs[job_id]


def search_memory(query: str, team_id: str = "demo-team") -> Dict[str, Any]:
    _ensure_initialized()
    try:
        return _recall.answer(query, team_id, trace_id="trace-search")
    except Exception as exc:
        raise classify_processing_error(exc, "memory_search") from exc


def pre_meeting_brief(payload: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_initialized()
    agenda = payload.get("agenda", [])
    if isinstance(agenda, str):
        agenda = [line.strip() for line in agenda.splitlines() if line.strip()]
    agenda = _string_list(agenda, "agenda")
    if not agenda:
        raise MalformedTranscriptError("agenda must include at least one topic")
    try:
        result = _recall.pre_meeting_brief(
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
    _ensure_initialized()
    if resolver_role not in _allowed_resolution_roles():
        raise AuthorizationError(
            "Only team leads, decision owners, or admins can resolve conflicts.",
            detail={"resolver_role": resolver_role, "decision_id": decision_id},
        )
    try:
        updated = _memory.update_decision(decision_id, status="resolved", resolved_by=resolver, resolution_note=note)
    except Exception as exc:
        raise classify_processing_error(exc, "decision_resolve") from exc
    if not updated:
        return {"error": "Decision not found", "decision_id": decision_id}
    trace_event("conflict_resolution", "resolved", {"decision_id": decision_id, "resolver": resolver, "resolver_role": resolver_role})
    return {"decision": updated}


def list_unresolved_conflicts(team_id: str = "demo-team") -> Dict[str, Any]:
    _ensure_initialized()
    try:
        conflicts = _memory.list_decisions(team_id=team_id, status="conflicted", limit=100)
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
