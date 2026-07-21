from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.memory import LocalVectorMemory
from backend.app.services.pipeline import MeetingPipeline


def main() -> None:
    memory = LocalVectorMemory(str(ROOT / "backend" / "app" / "memory" / "local_ledger.json"))
    memory.reset()
    pipeline = MeetingPipeline(memory)
    pipeline.process(
        "Platform architecture kickoff",
        "demo-team",
        "Asha Rao: We decided use Qdrant as the persistent vector ledger. Marco will prepare the ingestion checklist by Friday.",
        attendees=["Asha Rao", "Marco Lee"],
        agenda=["memory ledger", "ingestion"],
    )
    pipeline.process(
        "Platform architecture follow-up",
        "demo-team",
        "Decision: no longer use Qdrant as the persistent vector ledger. Maybe replace it with a relational table.",
        attendees=["Asha Rao"],
        agenda=["memory ledger"],
    )
    print("Seeded demo data with an active decision and one conflicted decision.")


if __name__ == "__main__":
    main()
