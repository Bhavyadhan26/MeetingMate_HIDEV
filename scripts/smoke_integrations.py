from __future__ import annotations

from pathlib import Path
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agents.adk_runtime import detect_adk_runtime
from backend.app.memory.vector_store import LocalVectorMemory, QdrantVectorMemory
from backend.app.models.schemas import Decision
from backend.app.observability import trace_event


def smoke_local_memory() -> None:
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    path = Path(tmp.name)
    path.unlink(missing_ok=True)
    memory = LocalVectorMemory(str(path))
    decision = Decision(
        meeting_id="meeting-smoke",
        team_id="smoke",
        text="use Qdrant for vector memory",
        source_excerpt="We decided use Qdrant for vector memory.",
    )
    memory.upsert_decision(decision)
    hits = memory.search_decisions("vector memory", "smoke")
    assert hits and hits[0]["id"] == decision.id
    path.unlink(missing_ok=True)
    print("local_memory=ok")


def smoke_qdrant() -> None:
    if os.getenv("SMOKE_QDRANT", "").lower() not in {"1", "true", "yes"}:
        print("qdrant=skipped set SMOKE_QDRANT=1 to require a live Qdrant check")
        return
    memory = QdrantVectorMemory(os.getenv("QDRANT_URL", "http://localhost:6333"), os.getenv("QDRANT_API_KEY", ""))
    decision = Decision(
        meeting_id="meeting-smoke",
        team_id="smoke",
        text="use Qdrant for vector memory",
        source_excerpt="We decided use Qdrant for vector memory.",
    )
    memory.upsert_decision(decision)
    hits = memory.search_decisions("vector memory", "smoke")
    assert hits and hits[0]["id"] == decision.id
    print("qdrant=ok")


def smoke_adk() -> None:
    status = detect_adk_runtime()
    print(f"adk_available={status.available} detail={status.detail} version={status.version}")


def smoke_trace() -> None:
    trace_id = trace_event("smoke", "integration", {"component": "script"})
    print(f"trace=ok trace_id={trace_id}")


def main() -> None:
    smoke_local_memory()
    smoke_adk()
    smoke_trace()
    smoke_qdrant()


if __name__ == "__main__":
    main()
