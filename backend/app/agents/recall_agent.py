from __future__ import annotations

from backend.app.memory import LocalVectorMemory
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
