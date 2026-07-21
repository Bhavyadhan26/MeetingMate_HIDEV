from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4


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
    return trace_id
