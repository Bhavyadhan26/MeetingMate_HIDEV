from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from backend.app.agents.adk_runtime import detect_adk_runtime, run_adk_extraction_graph
from backend.app.agents.action_item_extractor import ActionItemExtractorAgent
from backend.app.agents.decision_drift_agent import DecisionDriftAgent
from backend.app.agents.decision_extractor import DecisionExtractorAgent
from backend.app.agents.summarizer import SummarizerAgent
from backend.app.memory import LocalVectorMemory
from backend.app.models import Meeting, ProcessingResult, Transcript
from backend.app.observability import trace_event


class MeetingAgentManager:
    """Manager that mirrors ADK parallel-then-sequential orchestration."""

    name = "manager"

    def __init__(self, memory: LocalVectorMemory) -> None:
        self.memory = memory
        self.summarizer = SummarizerAgent()
        self.actions = ActionItemExtractorAgent()
        self.decisions = DecisionExtractorAgent()
        self.drift = DecisionDriftAgent(memory)

    def run(self, meeting: Meeting, transcript: Transcript) -> ProcessingResult:
        trace_id = f"trace-{uuid4().hex[:12]}"
        adk_status = detect_adk_runtime()
        orchestration = "adk parallel extraction, sequential drift write" if adk_status.available else "threaded fallback parallel extraction, sequential drift write"
        trace_event(self.name, "start", {
            "trace_id": trace_id,
            "meeting_id": meeting.id,
            "orchestration": orchestration,
            "adk_available": adk_status.available,
            "adk_detail": adk_status.detail,
            "adk_version": adk_status.version,
        })
        if adk_status.available:
            try:
                extraction = run_adk_extraction_graph(
                    meeting=meeting,
                    transcript=transcript,
                    trace_id=trace_id,
                    summarizer=self.summarizer,
                    action_item_extractor=self.actions,
                    decision_extractor=self.decisions,
                )
                summary = extraction["summary"]
                action_items = extraction["action_items"]
                decisions = extraction["decisions"]
                possible = extraction["possible_decisions"]
                trace_event(self.name, "adk_graph_finish", {
                    "trace_id": trace_id,
                    "root_agent": extraction["root_agent"],
                    "parallel_agent": extraction["parallel_agent"],
                    "event_count": extraction["event_count"],
                })
            except Exception as exc:
                trace_event(self.name, "adk_graph_error", {"trace_id": trace_id, "error": str(exc)})
                summary, action_items, decisions, possible = self._run_threaded_extraction(meeting, transcript, trace_id)
        else:
            summary, action_items, decisions, possible = self._run_threaded_extraction(meeting, transcript, trace_id)

        persisted = [self.drift.write_with_status(decision, trace_id) for decision in decisions]
        trace_event(self.name, "finish", {"trace_id": trace_id, "decisions": len(persisted), "action_items": len(action_items)})
        return ProcessingResult(meeting=meeting, transcript=transcript, summary=summary, action_items=action_items, decisions=persisted, possible_decisions=possible, trace_id=trace_id)

    def _run_threaded_extraction(self, meeting: Meeting, transcript: Transcript, trace_id: str):
        with ThreadPoolExecutor(max_workers=3) as pool:
            summary_future = pool.submit(self.summarizer.run, transcript, trace_id)
            actions_future = pool.submit(self.actions.run, meeting, transcript, trace_id)
            decisions_future = pool.submit(self.decisions.run, meeting, transcript, trace_id)
            summary = summary_future.result()
            action_items = actions_future.result()
            decisions, possible = decisions_future.result()
        return summary, action_items, decisions, possible
