from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LYZR_BASE_URL = "https://rag-prod.studio.lyzr.ai"
DEFAULT_COLLECTION = "decisions"


def main() -> int:
    load_dotenv(ROOT / ".env")
    try:
        result = sync_decisions_to_lyzr()
    except RuntimeError as exc:
        print(json.dumps({"lyzr_sync_qdrant_decisions": "failed", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def sync_decisions_to_lyzr() -> dict[str, Any]:
    qdrant_url = os.getenv("QDRANT_URL", "").strip().rstrip("/")
    qdrant_key = os.getenv("QDRANT_API_KEY", "").strip()
    qdrant_collection = os.getenv("LYZR_SYNC_QDRANT_COLLECTION", DEFAULT_COLLECTION).strip()
    lyzr_api_key = os.getenv("LYZR_API_KEY", "").strip()
    rag_id = os.getenv("LYZR_RAG_ID", "").strip()
    lyzr_base_url = os.getenv("LYZR_RAG_BASE_URL", DEFAULT_LYZR_BASE_URL).strip().rstrip("/")
    team_id = os.getenv("LYZR_SYNC_TEAM_ID", "").strip()
    dry_run = os.getenv("LYZR_SYNC_DRY_RUN", "").lower() in {"1", "true", "yes"}
    if not qdrant_url:
        raise RuntimeError("Set QDRANT_URL before syncing decisions into Lyzr.")
    if not qdrant_collection:
        raise RuntimeError("Set LYZR_SYNC_QDRANT_COLLECTION or use the default decisions collection.")
    if not lyzr_api_key:
        raise RuntimeError("Set LYZR_API_KEY before syncing decisions into Lyzr.")
    if not rag_id:
        raise RuntimeError("Set LYZR_RAG_ID to the Lyzr Knowledge Base/RAG id before syncing decisions.")

    decisions = load_qdrant_decisions(qdrant_url, qdrant_key, qdrant_collection, team_id=team_id or None)
    documents = build_lyzr_documents(decisions)
    if not documents:
        raise RuntimeError("No Qdrant decisions were found to sync into Lyzr.")

    if dry_run:
        return {
            "lyzr_sync_qdrant_decisions": "dry_run",
            "rag_id": rag_id,
            "qdrant_collection": qdrant_collection,
            "decision_count": len(decisions),
            "document_count": len(documents),
            "first_source": documents[0]["source"],
        }

    payload = {
        "data": documents,
        "chunk_size": int(os.getenv("LYZR_SYNC_CHUNK_SIZE", "1000")),
        "chunk_overlap": int(os.getenv("LYZR_SYNC_CHUNK_OVERLAP", "100")),
    }
    response = train_lyzr_text(lyzr_base_url, lyzr_api_key, rag_id, payload)
    return {
        "lyzr_sync_qdrant_decisions": "submitted",
        "rag_id": rag_id,
        "qdrant_collection": qdrant_collection,
        "decision_count": len(decisions),
        "document_count": len(documents),
        "response": response,
        "next_step": "Run scripts/lyzr_rag_retrieve_check.py after Lyzr finishes training the submitted text.",
    }


def load_qdrant_decisions(qdrant_url: str, api_key: str, collection: str, *, team_id: str | None) -> list[dict[str, Any]]:
    limit = int(os.getenv("LYZR_SYNC_SCROLL_LIMIT", "100"))
    max_points = int(os.getenv("LYZR_SYNC_MAX_POINTS", "1000"))
    offset: Any = None
    decisions: list[dict[str, Any]] = []
    while len(decisions) < max_points:
        body: dict[str, Any] = {"limit": min(limit, max_points - len(decisions)), "with_payload": True, "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        if team_id:
            body["filter"] = {"must": [{"key": "team_id", "match": {"value": team_id}}]}
        page = qdrant_post_json(f"{qdrant_url}/collections/{collection}/points/scroll", api_key, body)
        result = page.get("result", {})
        points = result.get("points", [])
        if not isinstance(points, list):
            raise RuntimeError("Qdrant scroll returned an unexpected points shape.")
        for point in points:
            payload = point.get("payload") if isinstance(point, dict) else None
            if isinstance(payload, dict) and payload.get("text"):
                decisions.append(payload)
        offset = result.get("next_page_offset")
        if not offset or not points:
            break
    return _dedupe_decisions(decisions)


def _dedupe_decisions(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for decision in decisions:
        identity = str(decision.get("id") or decision.get("text"))
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(decision)
    return unique


def build_lyzr_documents(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for decision in decisions:
        drift = decision.get("drift") if isinstance(decision.get("drift"), dict) else {}
        text = "\n".join(
            [
                f"Decision: {decision.get('text', '')}",
                f"Status: {decision.get('status', '')}",
                f"Team: {decision.get('team_id', '')}",
                f"Meeting ID: {decision.get('meeting_id', '')}",
                f"Source excerpt: {decision.get('source_excerpt', '')}",
                f"Drift label: {drift.get('label', '')}",
                f"Drift rationale: {drift.get('rationale', '')}",
                f"Prior decision id: {drift.get('prior_decision_id', '')}",
                f"Created at: {decision.get('created_at', '')}",
            ]
        ).strip()
        documents.append(
            {
                "text": text,
                "source": f"meetingmate-qdrant-decision-{decision.get('id', 'unknown')}",
                "extra_info": {
                    "decision_id": decision.get("id"),
                    "meeting_id": decision.get("meeting_id"),
                    "team_id": decision.get("team_id"),
                    "status": decision.get("status"),
                    "source": "MeetingMate Qdrant decisions collection",
                },
            }
        )
    return documents


def qdrant_post_json(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    headers = {"accept": "application/json", "content-type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    return post_json(url, payload, headers, timeout=30)


def train_lyzr_text(base_url: str, api_key: str, rag_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    params = urllib.parse.urlencode({"rag_id": rag_id})
    return post_json(
        f"{base_url}/v3/train/text/?{params}",
        payload,
        {"accept": "application/json", "content-type": "application/json", "x-api-key": api_key},
        timeout=120,
    )


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {url} returned status={exc.code} response={detail!r}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"POST {url} failed: {exc}") from exc
    if not body.strip():
        return {}
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"POST {url} returned non-JSON response: {body[:300]!r}") from exc
    if isinstance(data, dict):
        return data
    return {"value": data}


if __name__ == "__main__":
    raise SystemExit(main())
