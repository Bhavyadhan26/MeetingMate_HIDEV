from __future__ import annotations

import re
from typing import List, Tuple

from backend.app.models.schemas import Decision, Meeting, PossibleDecision, Transcript
from backend.app.observability import trace_event


DECISION_RE = re.compile(r"(?:we\s+(?:decided|agreed|approved|committed)|decision:)\s+(?P<decision>[^.]+)\.", re.I)
POSSIBLE_RE = re.compile(r"(?:maybe|might|consider|leaning toward|proposal:)\s+(?P<decision>[^.]+)\.", re.I)


class DecisionExtractorAgent:
    name = "decision_extractor"

    def run(self, meeting: Meeting, transcript: Transcript, trace_id: str) -> Tuple[List[Decision], List[PossibleDecision]]:
        trace_event(self.name, "start", {"trace_id": trace_id, "meeting_id": meeting.id})
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
