from __future__ import annotations

from backend.app.agents import MeetingAgentManager
from backend.app.memory import LocalVectorMemory
from backend.app.models import Meeting, ProcessingResult, Transcript
from backend.app.services.redaction import redact_pii


class MeetingPipeline:
    def __init__(self, memory: LocalVectorMemory) -> None:
        self.memory = memory
        self.manager = MeetingAgentManager(memory)

    def process(self, title: str, team_id: str, transcript_text: str, attendees: list[str] | None = None, agenda: list[str] | None = None) -> ProcessingResult:
        meeting = Meeting(team_id=team_id, title=title, attendees=attendees or [], agenda=agenda or [])
        redacted_text, redaction_map = redact_pii(transcript_text, attendees or [])
        transcript = Transcript(meeting_id=meeting.id, team_id=team_id, raw_text=transcript_text, redacted_text=redacted_text, redaction_map=redaction_map)
        return self.manager.run(meeting, transcript)
