from __future__ import annotations

import re
from backend.app.models import Summary, Transcript
from backend.app.observability import trace_event


class SummarizerAgent:
    name = "summarizer"

    def run(self, transcript: Transcript, trace_id: str) -> Summary:
        trace_event(self.name, "start", {"trace_id": trace_id, "meeting_id": transcript.meeting_id})
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", transcript.redacted_text) if part.strip()]
        key_points = sentences[:4] or [transcript.redacted_text[:180]]
        tldr = key_points[0][:220] if key_points else "No substantive meeting content found."
        summary = Summary(tldr=tldr, key_points=key_points)
        trace_event(self.name, "finish", {"trace_id": trace_id, "key_points": len(key_points)})
        return summary
