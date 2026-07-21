from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from backend.app.memory.vector_store import LocalVectorMemory
from backend.app.observability.otlp_smoke import has_otlp_exporter
from backend.app.services.pipeline import MeetingPipeline

EXPECTED_AGENTS = {
    "manager",
    "summarizer",
    "action_item_extractor",
    "decision_extractor",
    "decision_drift_agent",
}


def run_live_lyzr_trace_check() -> dict:
    validate_configuration()
    trace_file = tempfile.NamedTemporaryFile(delete=False)
    trace_file.close()
    Path(trace_file.name).unlink(missing_ok=True)
    old_trace_path = os.environ.get("TRACE_OUTPUT_PATH")
    os.environ["TRACE_OUTPUT_PATH"] = trace_file.name
    try:
        from backend.app.observability.tracing import flush_traces, shutdown_traces

        memory_file = tempfile.NamedTemporaryFile(delete=False)
        memory_file.close()
        Path(memory_file.name).unlink(missing_ok=True)
        memory = LocalVectorMemory(memory_file.name)
        result = MeetingPipeline(memory).process(
            title="Lyzr live trace check",
            team_id="lyzr-live",
            transcript_text="Asha Rao: We decided use Qdrant for Lyzr-visible meeting memory. Marco will document the Lyzr trace check by Friday.",
            attendees=["Asha Rao", "Marco Lee"],
            agenda=["lyzr trace", "memory"],
        )
        flushed = flush_traces()
        records = [json.loads(line) for line in Path(trace_file.name).read_text(encoding="utf-8").splitlines() if line.strip()]
        agents = {record["agent"] for record in records if record.get("trace_id") == result.trace_id}
        missing = sorted(EXPECTED_AGENTS - agents)
        if missing:
            raise RuntimeError(f"Missing expected local trace agents before Lyzr verification: {missing}")
        errors = [record for record in records if record.get("event") == "otlp_exporter_error"]
        if errors:
            raise RuntimeError(f"OTLP exporter initialization failed: {errors[-1]['payload']}")
        Path(memory_file.name).unlink(missing_ok=True)
        return {
            "lyzr_live_trace_check": "submitted",
            "trace_id": result.trace_id,
            "orchestration": result.orchestration,
            "agents": sorted(agents),
            "flush_result": flushed,
            "lyzr_otlp_endpoint": os.environ["LYZR_OTLP_ENDPOINT"],
            "next_step": "Open Lyzr Studio and verify this trace id / service.name meetingmate-agent-swarm is visible.",
        }
    finally:
        try:
            shutdown_traces()
        except UnboundLocalError:
            pass
        Path(trace_file.name).unlink(missing_ok=True)
        if old_trace_path is None:
            os.environ.pop("TRACE_OUTPUT_PATH", None)
        else:
            os.environ["TRACE_OUTPUT_PATH"] = old_trace_path


def validate_configuration() -> None:
    endpoint = os.getenv("LYZR_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("Set LYZR_OTLP_ENDPOINT to the Lyzr OTLP trace endpoint before running this check.")
    has_auth = bool(os.getenv("LYZR_API_KEY", "").strip() or os.getenv("LYZR_OTLP_HEADERS", "").strip())
    if not has_auth:
        raise RuntimeError("Set LYZR_API_KEY or LYZR_OTLP_HEADERS so the Lyzr collector can authenticate the trace export.")
    if not has_otlp_exporter():
        raise RuntimeError("OpenTelemetry SDK/exporter is not installed. Run this in the backend container or install backend requirements.")


def main() -> int:
    try:
        result = run_live_lyzr_trace_check()
    except RuntimeError as exc:
        print(json.dumps({"lyzr_live_trace_check": "not_submitted", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
