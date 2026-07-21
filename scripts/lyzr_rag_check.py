from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://rag-prod.studio.lyzr.ai"


def main() -> int:
    load_dotenv(ROOT / ".env")
    try:
        result = verify_lyzr_rag()
    except RuntimeError as exc:
        print(json.dumps({"lyzr_rag_check": "failed", "error": str(exc)}, indent=2))
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


def verify_lyzr_rag() -> dict[str, Any]:
    api_key = os.getenv("LYZR_API_KEY", "").strip()
    rag_id = os.getenv("LYZR_RAG_ID", "").strip()
    expected_collection = os.getenv("LYZR_RAG_COLLECTION", "decisions").strip()
    base_url = os.getenv("LYZR_RAG_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    if not api_key:
        raise RuntimeError("Set LYZR_API_KEY before running the Lyzr RAG check.")
    if not rag_id:
        raise RuntimeError("Set LYZR_RAG_ID to the Lyzr Knowledge Base/RAG id before running this check.")
    url = f"{base_url}/v3/rag/{rag_id}/"
    payload = request_json(url, api_key)
    collection_name = str(payload.get("collection_name", ""))
    provider = str(payload.get("vector_store_provider", ""))
    if expected_collection and expected_collection not in collection_name:
        raise RuntimeError(
            f"Lyzr RAG collection {collection_name!r} does not match expected substring {expected_collection!r}."
        )
    if "qdrant" not in provider.lower():
        raise RuntimeError(f"Lyzr RAG provider {provider!r} is not Qdrant.")
    return {
        "lyzr_rag_check": "ok",
        "rag_id": payload.get("id", rag_id),
        "collection_name": collection_name,
        "vector_store_provider": provider,
        "llm_model": payload.get("llm_model"),
        "embedding_model": payload.get("embedding_model"),
        "semantic_data_model": payload.get("semantic_data_model"),
        "multi_tenancy_enabled": payload.get("multi_tenancy_enabled"),
        "next_step": "Attach this Knowledge Base to a Lyzr agent and invoke it; inspect the run in Lyzr Studio Monitoring > Traces.",
    }


def request_json(url: str, api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"accept": "application/json", "x-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read(300).decode("utf-8", errors="replace")
        raise RuntimeError(f"Lyzr RAG API returned status={exc.code} response={detail!r}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Lyzr RAG API request failed: {exc}") from exc
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Lyzr RAG API returned non-JSON response: {body[:300]!r}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Lyzr RAG API returned an unexpected non-object response.")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
