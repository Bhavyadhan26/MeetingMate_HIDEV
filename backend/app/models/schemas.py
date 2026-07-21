from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover - lets smoke tests run before dependencies are installed
    class _FieldDefault:
        def __init__(self, default: Any = None, default_factory: Any = None) -> None:
            self.default = default
            self.default_factory = default_factory

        def value(self) -> Any:
            if self.default_factory is not None:
                return self.default_factory()
            return self.default

    def _dump(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [_dump(item) for item in value]
        if isinstance(value, dict):
            return {key: _dump(item) for key, item in value.items()}
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return value

    class BaseModel:
        def __init__(self, **data: Any) -> None:
            annotations = getattr(self.__class__, "__annotations__", {})
            for name in annotations:
                if name in data:
                    setattr(self, name, data[name])
                elif hasattr(self.__class__, name):
                    default = getattr(self.__class__, name)
                    if isinstance(default, _FieldDefault):
                        setattr(self, name, default.value())
                    else:
                        setattr(self, name, default)
            for name, value in data.items():
                if not hasattr(self, name):
                    setattr(self, name, value)

        def model_dump(self) -> Dict[str, Any]:
            return {key: _dump(value) for key, value in self.__dict__.items()}

    def Field(default: Any = None, default_factory: Any = None, **_: Any) -> Any:
        return _FieldDefault(default, default_factory)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DecisionStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CONFLICTED = "conflicted"
    RESOLVED = "resolved"


class DriftLabel(str, Enum):
    NEW = "New"
    RELATED = "Related"
    POTENTIAL_CONFLICT = "Potential Conflict"


class Meeting(BaseModel):
    id: str = Field(default_factory=lambda: f"meeting-{uuid4().hex[:10]}")
    team_id: str
    title: str
    attendees: List[str] = Field(default_factory=list)
    agenda: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class Transcript(BaseModel):
    meeting_id: str
    team_id: str
    raw_text: str
    redacted_text: str = ""
    redaction_map: Dict[str, str] = Field(default_factory=dict)


class MeetingChunk(BaseModel):
    id: str = Field(default_factory=lambda: f"chunk-{uuid4().hex[:10]}")
    meeting_id: str
    team_id: str
    speaker: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    text: str
    redacted_text: str
    source_index: int = 0


class Summary(BaseModel):
    tldr: str
    key_points: List[str] = Field(default_factory=list)


class ActionItem(BaseModel):
    id: str = Field(default_factory=lambda: f"action-{uuid4().hex[:10]}")
    meeting_id: str
    team_id: str
    task: str
    owner: str = "Unassigned"
    deadline: Optional[str] = None
    source_excerpt: str


class DriftClassification(BaseModel):
    label: DriftLabel
    rationale: str
    prior_decision_id: Optional[str] = None
    prior_source_excerpt: Optional[str] = None
    score: float = 0.0


class Decision(BaseModel):
    id: str = Field(default_factory=lambda: f"decision-{uuid4().hex[:10]}")
    meeting_id: str
    team_id: str
    text: str
    source_excerpt: str
    status: DecisionStatus = DecisionStatus.ACTIVE
    related_decision_ids: List[str] = Field(default_factory=list)
    drift: Optional[DriftClassification] = None
    created_at: datetime = Field(default_factory=utcnow)
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None


class PossibleDecision(BaseModel):
    text: str
    reason: str
    source_excerpt: str


class ProcessingResult(BaseModel):
    meeting: Meeting
    transcript: Transcript
    summary: Summary
    meeting_chunks: List[MeetingChunk] = Field(default_factory=list)
    action_items: List[ActionItem]
    decisions: List[Decision]
    possible_decisions: List[PossibleDecision] = Field(default_factory=list)
    trace_id: str


class DecisionCitation(BaseModel):
    decision_id: str
    text: str
    source_excerpt: str
    status: str
    score: float


class AgendaTopicBrief(BaseModel):
    topic: str
    summary: str
    citations: List[DecisionCitation] = Field(default_factory=list)


class PreMeetingBrief(BaseModel):
    team_id: str
    agenda: List[str]
    topics: List[AgendaTopicBrief] = Field(default_factory=list)
    trace_id: str
