from __future__ import annotations

import re
from typing import List, Tuple

from backend.app.models.schemas import Decision, Meeting, PossibleDecision, Transcript
from backend.app.observability import trace_event
from backend.app.agents.groq_llm import chat_json, groq_enabled


DECISION_RE = re.compile(r"(?:we\s+(?:decided|agreed|approved|committed)|decision:)\s+(?P<decision>[^.]+)\.", re.I)
POSSIBLE_RE = re.compile(r"(?:maybe|might|consider|leaning toward|proposal:)\s+(?P<decision>[^.]+)\.", re.I)


class DecisionExtractorAgent:
    name = "decision_extractor"

    def run(self, meeting: Meeting, transcript: Transcript, trace_id: str) -> Tuple[List[Decision], List[PossibleDecision]]:
        trace_event(self.name, "start", {"trace_id": trace_id, "meeting_id": meeting.id})
        if groq_enabled():
            try:
                payload = chat_json(
                    "Extract only explicit, verbatim-grounded meeting decisions. Return JSON with decisions and possible_decisions arrays. decisions items need text and source_excerpt. possible_decisions items need text, reason, source_excerpt. Do not invent decisions.",
                    f"Transcript:\n{transcript.redacted_text}",
                    max_tokens=1600,
                )
                decisions = [
                    Decision(
                        meeting_id=meeting.id,
                        team_id=meeting.team_id,
                        text=str(item.get("text") or "").strip(),
                        source_excerpt=str(item.get("source_excerpt") or "").strip(),
                    )
                    for item in payload.get("decisions", [])
                    if isinstance(item, dict) and str(item.get("text") or "").strip() and str(item.get("source_excerpt") or "").strip()
                ]
                possible = [
                    PossibleDecision(
                        text=str(item.get("text") or "").strip(),
                        reason=str(item.get("reason") or "Ambiguous decision language."),
                        source_excerpt=str(item.get("source_excerpt") or "").strip(),
                    )
                    for item in payload.get("possible_decisions", [])
                    if isinstance(item, dict) and str(item.get("text") or "").strip()
                ]
                trace_event(self.name, "finish", {"trace_id": trace_id, "decisions": len(decisions), "possible_decisions": len(possible), "provider": "groq"})
                return decisions, possible
            except Exception as exc:
                trace_event(self.name, "groq_error", {"trace_id": trace_id, "error": str(exc)})
        decisions: List[Decision] = []
        possible: List[PossibleDecision] = []
        for match in DECISION_RE.finditer(transcript.redacted_text):
            text = match.group("decision").strip()
            if len(text) >= 8:
                decisions.append(Decision(meeting_id=meeting.id, team_id=meeting.team_id, text=text, source_excerpt=match.group(0).strip()))
        for match in POSSIBLE_RE.finditer(transcript.redacted_text):
            possible.append(PossibleDecision(text=match.group("decision").strip(), reason="Ambiguous language was used.", source_excerpt=match.group(0).strip()))
        trace_event(self.name, "finish", {"trace_id": trace_id, "decisions": len(decisions), "possible_decisions": len(possible)})
        return decisions, possible
