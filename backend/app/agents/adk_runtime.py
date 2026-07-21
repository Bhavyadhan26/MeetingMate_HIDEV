from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ADKRuntimeStatus:
    available: bool
    detail: str
    version: Optional[str] = None


def detect_adk_runtime() -> ADKRuntimeStatus:
    """Detect Google ADK without making local tests depend on it."""
    try:
        import importlib.metadata

        version = importlib.metadata.version("google-adk")
        __import__("google.adk")
        return ADKRuntimeStatus(True, "google.adk import succeeded", version)
    except Exception as exc:  # pragma: no cover - depends on optional runtime
        return ADKRuntimeStatus(False, f"Google ADK unavailable: {exc}")


def _run_coro_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def run_adk_extraction_graph(
    *,
    meeting: Any,
    transcript: Any,
    trace_id: str,
    summarizer: Any,
    action_item_extractor: Any,
    decision_extractor: Any,
) -> dict[str, Any]:
    """Run the independent extraction agents through ADK primitives.

    The production dependency is optional for local tests. When google-adk is
    installed, this constructs a real ADK graph:

    SequentialAgent(
      ParallelAgent(summarizer, action_item_extractor, decision_extractor)
    )

    State deltas from the wrapped deterministic agents become the handoff
    contract back to the business pipeline.
    """

    async def _run() -> dict[str, Any]:
        from google.adk.agents import BaseAgent, ParallelAgent, SequentialAgent
        from google.adk.events import Event, EventActions
        from google.adk.runners import InMemoryRunner
        from google.genai import types
        from pydantic import ConfigDict

        class FunctionAgent(BaseAgent):
            model_config = ConfigDict(arbitrary_types_allowed=True)

            worker: Any
            output_key: str
            meeting_input: Any = None
            transcript_input: Any

            async def _run_async_impl(self, ctx):
                if self.meeting_input is None:
                    output = self.worker.run(self.transcript_input, trace_id)
                else:
                    output = self.worker.run(self.meeting_input, self.transcript_input, trace_id)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"{self.name} completed")], role="model"),
                    actions=EventActions(stateDelta={self.output_key: output}),
                )

        class DecisionFunctionAgent(FunctionAgent):
            async def _run_async_impl(self, ctx):
                decisions, possible = self.worker.run(self.meeting_input, self.transcript_input, trace_id)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"{self.name} completed")], role="model"),
                    actions=EventActions(stateDelta={"decisions": decisions, "possible_decisions": possible}),
                )

        extraction_parallel = ParallelAgent(
            name="parallel_extraction_swarm",
            description="Runs summary, action item, and conservative decision extraction concurrently.",
            sub_agents=[
                FunctionAgent(
                    name="summarizer_adk_agent",
                    description="Summarizes the redacted transcript.",
                    worker=summarizer,
                    output_key="summary",
                    transcript_input=transcript,
                ),
                FunctionAgent(
                    name="action_item_extractor_adk_agent",
                    description="Extracts grounded action items from the redacted transcript.",
                    worker=action_item_extractor,
                    output_key="action_items",
                    meeting_input=meeting,
                    transcript_input=transcript,
                ),
                DecisionFunctionAgent(
                    name="decision_extractor_adk_agent",
                    description="Extracts explicit grounded decisions and possible decisions.",
                    worker=decision_extractor,
                    output_key="decisions",
                    meeting_input=meeting,
                    transcript_input=transcript,
                ),
            ],
        )
        root_agent = SequentialAgent(
            name="meeting_intelligence_adk_manager",
            description="ADK manager that sequences the parallel extraction swarm before drift processing.",
            sub_agents=[extraction_parallel],
        )
        runner = InMemoryRunner(root_agent, app_name="meetingmate")
        session = await runner.session_service.create_session(
            app_name="meetingmate",
            user_id=meeting.team_id,
            session_id=trace_id,
            state={},
        )
        message = types.Content(parts=[types.Part(text=f"Process meeting {meeting.id}")], role="user")
        events = []
        async for event in runner.run_async(user_id=meeting.team_id, session_id=session.id, new_message=message):
            events.append(event)
        completed = await runner.session_service.get_session(app_name="meetingmate", user_id=meeting.team_id, session_id=session.id)
        return {
            "summary": completed.state["summary"],
            "action_items": completed.state["action_items"],
            "decisions": completed.state["decisions"],
            "possible_decisions": completed.state["possible_decisions"],
            "event_count": len(events),
            "root_agent": root_agent.name,
            "parallel_agent": extraction_parallel.name,
        }

    return _run_coro_sync(_run())
