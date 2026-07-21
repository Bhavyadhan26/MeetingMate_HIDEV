from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol
from uuid import NAMESPACE_URL, uuid5

from .embeddings import cosine, embed_text

VECTOR_SIZE = 64
DECISIONS_COLLECTION = "decisions"
ACTION_ITEMS_COLLECTION = "action_items"
MEETING_CHUNKS_COLLECTION = "meeting_chunks"


class VectorMemory(Protocol):
    def reset(self) -> None:
        ...

    def upsert_decision(self, decision: Any) -> None:
        ...

    def update_decision(self, decision_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        ...

    def search_decisions(self, query: str, team_id: str, limit: int = 5, status: Optional[str] = None) -> List[Dict[str, Any]]:
        ...


class LocalVectorMemory:
    def __init__(self, path: str = "backend/app/memory/local_ledger.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"decisions": [], "action_items": [], "meeting_chunks": []}, indent=2), encoding="utf-8")

    def _load(self) -> Dict[str, List[Dict[str, Any]]]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        self.path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def reset(self) -> None:
        self._save({"decisions": [], "action_items": [], "meeting_chunks": []})

    def upsert_decision(self, decision: Any) -> None:
        data = self._load()
        payload = decision.model_dump() if hasattr(decision, "model_dump") else dict(decision.__dict__)
        payload["vector"] = embed_text(payload["text"])
        data["decisions"] = [item for item in data["decisions"] if item["id"] != payload["id"]]
        data["decisions"].append(payload)
        self._save(data)

    def update_decision(self, decision_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        data = self._load()
        updated = None
        for item in data["decisions"]:
            if item["id"] == decision_id:
                item.update(fields)
                updated = item
        self._save(data)
        return updated

    def search_decisions(self, query: str, team_id: str, limit: int = 5, status: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._load()
        query_vector = embed_text(query)
        results: List[Dict[str, Any]] = []
        for item in data["decisions"]:
            if item.get("team_id") != team_id:
                continue
            if status and item.get("status") != status:
                continue
            scored = dict(item)
            scored["score"] = cosine(query_vector, item.get("vector", []))
            results.append(scored)
        return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]


class QdrantVectorMemory:
    """Qdrant-backed implementation of the same memory contract used locally."""

    def __init__(self, url: str, api_key: str = "") -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
        except Exception as exc:  # pragma: no cover - exercised only without optional dep
            raise RuntimeError("MEMORY_BACKEND=qdrant requires qdrant-client to be installed.") from exc

        self._models = __import__("qdrant_client.models", fromlist=["models"])
        self.client = QdrantClient(url=url, api_key=api_key or None)
        last_error: Optional[Exception] = None
        for collection in (DECISIONS_COLLECTION, ACTION_ITEMS_COLLECTION, MEETING_CHUNKS_COLLECTION):
            for _ in range(12):
                try:
                    if not self.client.collection_exists(collection):
                        self.client.create_collection(
                            collection_name=collection,
                            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                        )
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    time.sleep(1)
            if last_error is not None:
                raise RuntimeError(f"Could not initialize Qdrant collection {collection}: {last_error}") from last_error

    @staticmethod
    def _point_id(decision_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"meetingmate:{decision_id}"))

    def reset(self) -> None:
        for collection in (DECISIONS_COLLECTION, ACTION_ITEMS_COLLECTION, MEETING_CHUNKS_COLLECTION):
            if self.client.collection_exists(collection):
                self.client.delete_collection(collection)
        self.__init__(os.getenv("QDRANT_URL", "http://localhost:6333"), os.getenv("QDRANT_API_KEY", ""))

    def upsert_decision(self, decision: Any) -> None:
        PointStruct = self._models.PointStruct
        payload = decision.model_dump() if hasattr(decision, "model_dump") else dict(decision.__dict__)
        vector = embed_text(payload["text"])
        payload.pop("vector", None)
        self.client.upsert(
            collection_name=DECISIONS_COLLECTION,
            points=[PointStruct(id=self._point_id(payload["id"]), vector=vector, payload=payload)],
        )

    def update_decision(self, decision_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        point_id = self._point_id(decision_id)
        points = self.client.retrieve(collection_name=DECISIONS_COLLECTION, ids=[point_id], with_payload=True)
        if not points:
            return None
        updated = dict(points[0].payload or {})
        updated.update(fields)
        self.client.set_payload(collection_name=DECISIONS_COLLECTION, payload=fields, points=[point_id])
        return updated

    def search_decisions(self, query: str, team_id: str, limit: int = 5, status: Optional[str] = None) -> List[Dict[str, Any]]:
        FieldCondition = self._models.FieldCondition
        Filter = self._models.Filter
        MatchValue = self._models.MatchValue
        conditions = [FieldCondition(key="team_id", match=MatchValue(value=team_id))]
        if status:
            conditions.append(FieldCondition(key="status", match=MatchValue(value=status)))
        hits = self.client.search(
            collection_name=DECISIONS_COLLECTION,
            query_vector=embed_text(query),
            query_filter=Filter(must=conditions),
            limit=limit,
            with_payload=True,
        )
        results: List[Dict[str, Any]] = []
        for hit in hits:
            payload = dict(hit.payload or {})
            payload["score"] = float(hit.score)
            results.append(payload)
        return results


def get_memory() -> VectorMemory:
    backend = os.getenv("MEMORY_BACKEND", "local").lower()
    if backend == "qdrant":
        return QdrantVectorMemory(os.getenv("QDRANT_URL", "http://localhost:6333"), os.getenv("QDRANT_API_KEY", ""))
    return LocalVectorMemory(os.getenv("LOCAL_MEMORY_PATH", "backend/app/memory/local_ledger.json"))
