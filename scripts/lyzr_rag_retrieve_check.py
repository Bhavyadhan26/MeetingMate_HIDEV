from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://rag-prod.studio.lyzr.ai"
DEFAULT_QUERY = "What did we decide about Qdrant?"


def main() -> int:
    load_dotenv(ROOT / ".env")
    try:
        result = verify_retrieval()
    except RuntimeError as exc:
        print(json.dumps({"lyzr_rag_retrieve_check": "failed", "error": str(exc)}, indent=2))
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


def verify_retrieval() -> dict[str, Any]:
    api_key = os.getenv("LYZR_API_KEY", "").strip()
    rag_id = os.getenv("LYZR_RAG_ID", "").strip()
    query = os.getenv("LYZR_RAG_QUERY", DEFAULT_QUERY).strip()
    base_url = os.getenv("LYZR_RAG_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    if not api_key:
        raise RuntimeError("Set LYZR_API_KEY before running the Lyzr RAG retrieval check.")
    if not rag_id:
        raise RuntimeError("Set LYZR_RAG_ID to the Lyzr Knowledge Base/RAG id before running this check.")
    if not query:
        raise RuntimeError("Set LYZR_RAG_QUERY or use the default non-empty retrieval query.")
    params = urllib.parse.urlencode(
        {
            "query": query,
            "top_k": os.getenv("LYZR_RAG_TOP_K", "5"),
            "lambda_param": os.getenv("LYZR_RAG_LAMBDA", "0.6"),
            "retrieval_type": os.getenv("LYZR_RAG_RETRIEVAL_TYPE", "basic"),
            "score_threshold": os.getenv("LYZR_RAG_SCORE_THRESHOLD", "0"),
            "time_decay_factor": os.getenv("LYZR_RAG_TIME_DECAY_FACTOR", "0.7"),
        }
    )
    payload = request_json(f"{base_url}/v3/rag/{rag_id}/retrieve/?{params}", api_key)
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise RuntimeError("Lyzr RAG retrieve API returned an unexpected results shape.")
    if not results:
        raise RuntimeError(
            "Lyzr RAG retrieve returned zero results. Re-sync/populate the Knowledge Base collection and run again."
        )
    previews = [json.dumps(item, default=str)[:240] for item in results[:3]]
    return {
        "lyzr_rag_retrieve_check": "ok",
        "rag_id": rag_id,
        "query": query,
        "result_count": len(results),
        "result_previews": previews,
    }


def request_json(url: str, api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"accept": "application/json", "x-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(f"Lyzr RAG retrieve API returned status={exc.code} response={detail!r}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Lyzr RAG retrieve API request failed: {exc}") from exc
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Lyzr RAG retrieve API returned non-JSON response: {body[:300]!r}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Lyzr RAG retrieve API returned an unexpected non-object response.")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
