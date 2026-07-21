from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from backend.app.memory.vector_store import LocalVectorMemory
from backend.app.observability.otlp_smoke import _OtlpCaptureHandler, has_otlp_exporter
from backend.app.services.pipeline import MeetingPipeline


EXPECTED_AGENTS = {
    "manager",
    "summarizer",
    "action_item_extractor",
    "decision_extractor",
    "decision_drift_agent",
}


def run_pipeline_otlp_smoke() -> dict:
    if not has_otlp_exporter():
        raise RuntimeError("OpenTelemetry SDK/exporter is not installed in this Python runtime.")

    from http.server import HTTPServer
    import threading
    import time

    server = HTTPServer(("127.0.0.1", 0), _OtlpCaptureHandler)
    _OtlpCaptureHandler.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/traces"
    old_endpoint = os.environ.get("LYZR_OTLP_ENDPOINT")
    old_headers = os.environ.get("LYZR_OTLP_HEADERS")
    old_trace_path = os.environ.get("TRACE_OUTPUT_PATH")
    trace_file = tempfile.NamedTemporaryFile(delete=False)
    trace_file.close()
    Path(trace_file.name).unlink(missing_ok=True)
    os.environ["LYZR_OTLP_ENDPOINT"] = endpoint
    os.environ["LYZR_OTLP_HEADERS"] = json.dumps({"x-lyzr-smoke": "pipeline"})
    os.environ["TRACE_OUTPUT_PATH"] = trace_file.name
    try:
        from backend.app.observability.tracing import flush_traces, shutdown_traces

        memory_path = tempfile.NamedTemporaryFile(delete=False)
        memory_path.close()
        Path(memory_path.name).unlink(missing_ok=True)
        memory = LocalVectorMemory(memory_path.name)
        result = MeetingPipeline(memory).process(
            title="Pipeline OTLP smoke",
            team_id="otlp-smoke",
            transcript_text="Asha Rao: We decided use Qdrant for traceable meeting memory. Marco will document the trace checklist by Friday.",
            attendees=["Asha Rao", "Marco Lee"],
            agenda=["observability", "memory"],
        )
        flush_traces()
        deadline = time.time() + 5
        while time.time() < deadline and not _OtlpCaptureHandler.requests:
            time.sleep(0.05)
        if not _OtlpCaptureHandler.requests:
            raise RuntimeError("No OTLP request was received by the local smoke receiver.")
        records = [json.loads(line) for line in Path(trace_file.name).read_text(encoding="utf-8").splitlines() if line.strip()]
        agents = {record["agent"] for record in records if record.get("trace_id") == result.trace_id}
        missing = sorted(EXPECTED_AGENTS - agents)
        if missing:
            raise RuntimeError(f"Missing expected trace agents: {missing}")
        Path(memory_path.name).unlink(missing_ok=True)
        return {
            "trace_id": result.trace_id,
            "endpoint": endpoint,
            "orchestration": result.orchestration,
            "agents": sorted(agents),
            "requests": _OtlpCaptureHandler.requests,
        }
    finally:
        try:
            shutdown_traces()
        except UnboundLocalError:
            pass
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        Path(trace_file.name).unlink(missing_ok=True)
        restore_env("LYZR_OTLP_ENDPOINT", old_endpoint)
        restore_env("LYZR_OTLP_HEADERS", old_headers)
        restore_env("TRACE_OUTPUT_PATH", old_trace_path)


def restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


if __name__ == "__main__":
    print(json.dumps(run_pipeline_otlp_smoke(), indent=2))
