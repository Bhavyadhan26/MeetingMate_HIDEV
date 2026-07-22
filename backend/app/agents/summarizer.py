from __future__ import annotations

import re
from backend.app.models import Summary, Transcript
from backend.app.observability import trace_event
from backend.app.agents.groq_llm import chat_json, groq_enabled


class SummarizerAgent:
    name = "summarizer"

    def run(self, transcript: Transcript, trace_id: str) -> Summary:
        trace_event(self.name, "start", {"trace_id": trace_id, "meeting_id": transcript.meeting_id})
        if groq_enabled():
            try:
                payload = chat_json(
                    "You summarize meeting transcripts. Return JSON with keys tldr:string and key_points:array of concise strings.",
                    f"Transcript:\n{transcript.redacted_text}",
                    max_tokens=900,
                )
                key_points = [str(item).strip() for item in payload.get("key_points", []) if str(item).strip()]
                summary = Summary(tldr=str(payload.get("tldr") or "No substantive meeting content found."), key_points=key_points)
                trace_event(self.name, "finish", {"trace_id": trace_id, "key_points": len(summary.key_points), "provider": "groq"})
                return summary
            except Exception as exc:
                trace_event(self.name, "groq_error", {"trace_id": trace_id, "error": str(exc)})
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", transcript.redacted_text) if part.strip()]
        key_points = sentences[:4] or [transcript.redacted_text[:180]]
        tldr = key_points[0][:220] if key_points else "No substantive meeting content found."
        summary = Summary(tldr=tldr, key_points=key_points)
        trace_event(self.name, "finish", {"trace_id": trace_id, "key_points": len(key_points)})
        return summary
