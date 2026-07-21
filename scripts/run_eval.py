from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.memory import LocalVectorMemory
from backend.app.services.pipeline import MeetingPipeline


CASES = [
    ("We decided use Qdrant for vector search.", "Decision: no longer use Qdrant for vector search.", "Potential Conflict"),
    ("We agreed launch beta in September.", "Decision: launch beta in September with a waitlist.", "Related"),
    ("We decided keep billing in Stripe.", "We agreed add invoice exports for finance.", "New"),
    ("Decision: use Gemini Flash for extraction.", "Decision: stop using Gemini Flash for extraction.", "Potential Conflict"),
    ("We agreed store redaction maps for 30 days.", "Decision: store redaction maps for 30 days in encrypted storage.", "Related"),
    ("Decision: notify team leads on conflicts.", "We decided use Qdrant for transcript chunks.", "New"),
    ("We decided require source excerpts for decisions.", "Decision: no longer require source excerpts for decisions.", "Potential Conflict"),
    ("Decision: archive chunks after twelve months.", "Decision: archive chunks after twelve months to cold storage.", "Related"),
    ("We agreed use Auth0 for identity.", "Decision: cancel Auth0 for identity.", "Potential Conflict"),
    ("We decided route unresolved conflicts to PagerDuty.", "We agreed add a dashboard filter for action owners.", "New"),
]


def main() -> None:
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    path = Path(tmp.name)
    if path.exists():
        path.unlink()
    memory = LocalVectorMemory(str(path))
    pipeline = MeetingPipeline(memory)
    correct = 0
    rows = []
    for index, (prior, new, expected) in enumerate(CASES, start=1):
        team_id = f"eval-{index}"
        pipeline.process(f"Eval prior {index}", team_id, prior)
        result = pipeline.process(f"Eval new {index}", team_id, new)
        actual = result.decisions[0].drift.label.value if hasattr(result.decisions[0].drift.label, "value") else result.decisions[0].drift.label
        ok = actual == expected
        correct += int(ok)
        rows.append((index, expected, actual, ok))
    accuracy = correct / len(CASES)
    print("Decision Drift Eval")
    print(f"cases={len(CASES)} correct={correct} accuracy={accuracy:.2%}")
    for index, expected, actual, ok in rows:
        print(f"{index:02d} expected={expected} actual={actual} ok={ok}")
    path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
