from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

_TRACER = None


def _get_tracer() -> Any:
    global _TRACER
    if _TRACER is not None:
        return _TRACER
    endpoint = os.getenv("LYZR_OTLP_ENDPOINT", "")
    if not endpoint:
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": "meetingmate-agent-swarm"}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        _TRACER = trace.get_tracer("meetingmate")
        return _TRACER
    except Exception:
        return None


def trace_event(agent_name: str, event: str, payload: Dict[str, Any]) -> str:
    """Emit an inspectable local trace event and return its trace id.

    Deployments can point LYZR_OTLP_ENDPOINT at Lyzr's OTLP endpoint. The local
    JSONL trace is kept intentionally simple so tests and demos can prove that
    every agent ran even when remote credentials are unavailable.
    """
    trace_id = payload.get("trace_id") or f"trace-{uuid4().hex[:12]}"
    path = Path(os.getenv("TRACE_OUTPUT_PATH", "backend/app/observability/local_traces.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "trace_id": trace_id,
        "agent": agent_name,
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
        "lyzr_otlp_endpoint": os.getenv("LYZR_OTLP_ENDPOINT", ""),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    tracer = _get_tracer()
    if tracer is not None:
        with tracer.start_as_current_span(f"{agent_name}.{event}") as span:
            span.set_attribute("trace_id", trace_id)
            span.set_attribute("agent", agent_name)
            span.set_attribute("event", event)
            for key, value in payload.items():
                if isinstance(value, (str, bool, int, float)) or value is None:
                    span.set_attribute(f"payload.{key}", "" if value is None else value)
    return trace_id
