from __future__ import annotations

import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.memory import LocalVectorMemory
import backend.app.memory.vector_store as vector_store
from backend.app.services.pipeline import MeetingPipeline


CONFLICT_TOPICS = [
    ("use Qdrant for vector search", "no longer use Qdrant for vector search"),
    ("keep billing in Stripe", "stop keeping billing in Stripe"),
    ("require source excerpts for decisions", "no longer require source excerpts for decisions"),
    ("use Auth0 for identity", "cancel Auth0 for identity"),
    ("route unresolved conflicts to PagerDuty", "stop routing unresolved conflicts to PagerDuty"),
    ("store redaction maps for 30 days", "no longer store redaction maps for 30 days"),
    ("archive chunks after twelve months", "cancel archive chunks after twelve months"),
    ("use Deepgram for diarized transcripts", "stop using Deepgram for diarized transcripts"),
    ("write meeting metadata to Postgres", "no longer write meeting metadata to Postgres"),
    ("use Groq for extraction", "replace Groq for extraction"),
]

RELATED_TOPICS = [
    ("launch beta in September", "launch beta in September with a waitlist"),
    ("store redaction maps for 30 days", "store redaction maps for 30 days in encrypted storage"),
    ("archive chunks after twelve months", "archive chunks after twelve months to cold storage"),
    ("use Qdrant for transcript chunks", "use Qdrant for transcript chunks with team filters"),
    ("notify team leads on conflicts", "notify team leads on conflicts with a daily digest"),
    ("use Auth0 for identity", "use Auth0 for identity with organization claims"),
    ("persist job history in Postgres", "persist job history in Postgres with cleanup"),
    ("use Deepgram for audio upload", "use Deepgram for audio upload with diarization"),
    ("run extraction agents in parallel", "run extraction agents in parallel before drift checks"),
    ("require resolver notes", "require resolver notes on conflict closure"),
]

NEW_TOPICS = [
    ("use Qdrant for vector search", "add invoice exports for finance"),
    ("launch beta in September", "store audit logs for admin actions"),
    ("use Auth0 for identity", "compress uploaded audio after transcription"),
    ("notify team leads on conflicts", "add dashboard filters for action owners"),
    ("archive chunks after twelve months", "use dark mode in the frontend"),
    ("use Deepgram for audio upload", "rotate database backups weekly"),
    ("persist job history in Postgres", "add keyboard shortcuts to the UI"),
    ("require source excerpts for decisions", "publish a demo checklist"),
    ("write meeting metadata to Postgres", "add CSV export for action items"),
    ("use Groq for extraction", "increase frontend polling timeout"),
]


def build_cases() -> list[tuple[str, str, str]]:
    cases: list[tuple[str, str, str]] = []
    for _ in range(4):
        cases.extend((f"We decided {prior}.", f"Decision: {new}.", "Potential Conflict") for prior, new in CONFLICT_TOPICS)
        cases.extend((f"We agreed {prior}.", f"Decision: {new}.", "Related") for prior, new in RELATED_TOPICS)
        cases.extend((f"We decided {prior}.", f"We agreed {new}.", "New") for prior, new in NEW_TOPICS)
    return cases[:100]


def main() -> None:
    os.environ["GROQ_API_KEY"] = ""
    _install_eval_embedding_if_needed()
    cases = build_cases()
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    path = Path(tmp.name)
    if path.exists():
        path.unlink()
    memory = LocalVectorMemory(str(path))
    pipeline = MeetingPipeline(memory)
    rows = []
    labels = ["Potential Conflict", "Related", "New"]
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    for index, (prior, new, expected) in enumerate(cases, start=1):
        team_id = f"eval-{index}"
        pipeline.process(f"Eval prior {index}", team_id, prior)
        result = pipeline.process(f"Eval new {index}", team_id, new)
        actual = result.decisions[0].drift.label.value if hasattr(result.decisions[0].drift.label, "value") else result.decisions[0].drift.label
        confusion[expected][actual] += 1
        rows.append((index, expected, actual, actual == expected))
    correct = sum(1 for _, _, _, ok in rows if ok)
    print("Decision Drift Eval")
    print(f"cases={len(cases)} correct={correct} accuracy={correct / len(cases):.2%}")
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels if other != label)
        fn = sum(count for actual, count in confusion[label].items() if actual != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        print(f"{label}: precision={precision:.2%} recall={recall:.2%} f1={f1:.2%} support={sum(confusion[label].values())}")
    for index, expected, actual, ok in rows:
        print(f"{index:03d} expected={expected} actual={actual} ok={ok}")
    path.unlink(missing_ok=True)


def _install_eval_embedding_if_needed() -> None:
    try:
        import sentence_transformers  # noqa: F401
        return
    except Exception:
        pass

    def embed(text: str) -> list[float]:
        dimensions = 384
        vector = [0.0] * dimensions
        for token in text.lower().replace(".", " ").split():
            index = sum(ord(char) for char in token) % dimensions
            vector[index] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    vector_store.embed_text = embed


if __name__ == "__main__":
    main()
