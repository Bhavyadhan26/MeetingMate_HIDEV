from __future__ import annotations

import re
from typing import List

from backend.app.models import ActionItem, Meeting, Transcript
from backend.app.observability import trace_event
from backend.app.agents.groq_llm import chat_json, groq_enabled


ACTION_PATTERNS = [
    re.compile(r"(?P<owner>\[[A-Z]+_\d+\]|[A-Z][a-z]+)\s+(?:will|to|should)\s+(?P<task>[^.]+?)(?:\s+by\s+(?P<deadline>[^.]+))?\.", re.I),
    re.compile(r"Action item:\s*(?P<owner>[^-:]+)[-:]\s*(?P<task>[^.]+?)(?:\s+by\s+(?P<deadline>[^.]+))?\.", re.I),
]


class ActionItemExtractorAgent:
    name = "action_item_extractor"

    def run(self, meeting: Meeting, transcript: Transcript, trace_id: str) -> List[ActionItem]:
        trace_event(self.name, "start", {"trace_id": trace_id, "meeting_id": meeting.id})
        if groq_enabled():
            try:
                payload = chat_json(
                    "Extract grounded meeting action items. Return JSON: {\"action_items\":[{\"owner\":\"string\",\"task\":\"string\",\"deadline\":\"string|null\",\"source_excerpt\":\"verbatim excerpt\"}]}",
                    f"Attendees: {meeting.attendees}\nTranscript:\n{transcript.redacted_text}",
                    max_tokens=1400,
                )
                actions = [
                    ActionItem(
                        meeting_id=meeting.id,
                        team_id=meeting.team_id,
                        owner=str(item.get("owner") or "Unassigned"),
                        task=str(item.get("task") or "").strip(),
                        deadline=(str(item.get("deadline")).strip() if item.get("deadline") else None),
                        source_excerpt=str(item.get("source_excerpt") or "").strip(),
                    )
                    for item in payload.get("action_items", [])
                    if isinstance(item, dict) and str(item.get("task") or "").strip()
                ]
                trace_event(self.name, "finish", {"trace_id": trace_id, "action_items": len(actions), "provider": "groq"})
                return actions
            except Exception as exc:
                trace_event(self.name, "groq_error", {"trace_id": trace_id, "error": str(exc)})
        actions: List[ActionItem] = []
        for pattern in ACTION_PATTERNS:
            for match in pattern.finditer(transcript.redacted_text):
                task = match.group("task").strip()
                if len(task) < 4:
                    continue
                actions.append(ActionItem(
                    meeting_id=meeting.id,
                    team_id=meeting.team_id,
                    owner=match.group("owner").strip(),
                    task=task,
                    deadline=(match.groupdict().get("deadline") or "").strip() or None,
                    source_excerpt=match.group(0).strip(),
                ))
        trace_event(self.name, "finish", {"trace_id": trace_id, "action_items": len(actions)})
        return actions
