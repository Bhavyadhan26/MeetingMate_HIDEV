from __future__ import annotations

from backend.app.memory import LocalVectorMemory
from backend.app.models import AgendaTopicBrief, DecisionCitation, PreMeetingBrief
from backend.app.observability import trace_event


class RecallAgent:
    name = "recall_agent"

    def __init__(self, memory: LocalVectorMemory) -> None:
        self.memory = memory

    def answer(self, query: str, team_id: str, trace_id: str) -> dict:
        trace_event(self.name, "start", {"trace_id": trace_id, "query": query})
        hits = self.memory.search_decisions(query, team_id, limit=5)
        if not hits:
            answer = {"answer": "No related decisions were found.", "citations": []}
        else:
            citations = [{"decision_id": hit["id"], "text": hit["text"], "source_excerpt": hit["source_excerpt"], "status": hit["status"], "score": hit["score"]} for hit in hits]
            answer = {"answer": f"Most relevant decision: {hits[0]['text']}", "citations": citations}
        trace_event(self.name, "finish", {"trace_id": trace_id, "citations": len(answer["citations"])})
        return answer

    def pre_meeting_brief(self, agenda: list[str], team_id: str, trace_id: str) -> PreMeetingBrief:
        trace_event(self.name, "pre_meeting_brief_start", {"trace_id": trace_id, "team_id": team_id, "agenda_topics": len(agenda)})
        topics: list[AgendaTopicBrief] = []
        for topic in agenda:
            normalized = topic.strip()
            if not normalized:
                continue
            hits = self.memory.search_decisions(normalized, team_id, limit=3)
            citations = [
                DecisionCitation(
                    decision_id=hit["id"],
                    text=hit["text"],
                    source_excerpt=hit["source_excerpt"],
                    status=str(hit["status"]),
                    score=float(hit["score"]),
                )
                for hit in hits
            ]
            if citations:
                summary = f"{len(citations)} prior decision(s) may affect {normalized}."
            else:
                summary = f"No prior decisions found for {normalized}."
            topics.append(AgendaTopicBrief(topic=normalized, summary=summary, citations=citations))
        brief = PreMeetingBrief(team_id=team_id, agenda=[topic.topic for topic in topics], topics=topics, trace_id=trace_id)
        trace_event(self.name, "pre_meeting_brief_finish", {"trace_id": trace_id, "topics": len(brief.topics), "citations": sum(len(topic.citations) for topic in brief.topics)})
        return brief
