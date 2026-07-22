from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol
from uuid import NAMESPACE_URL, uuid5

from .embeddings import DIMENSIONS, cosine, embed_text

VECTOR_SIZE = DIMENSIONS
DECISIONS_COLLECTION = "decisions"
ACTION_ITEMS_COLLECTION = "action_items"
MEETING_CHUNKS_COLLECTION = "meeting_chunks"


class VectorMemory(Protocol):
    def reset(self) -> None:
        ...

    def upsert_decision(self, decision: Any) -> None:
        ...

    def upsert_action_item(self, action_item: Any) -> None:
        ...

    def upsert_meeting_chunk(self, meeting_chunk: Any) -> None:
        ...

    def update_decision(self, decision_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        ...

    def search_decisions(self, query: str, team_id: str, limit: int = 5, status: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    def list_decisions(self, team_id: str, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        ...

    def list_action_items(self, team_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        ...

    def list_meeting_chunks(self, team_id: str, limit: int = 50) -> List[Dict[str, Any]]:
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

    def upsert_action_item(self, action_item: Any) -> None:
        data = self._load()
        payload = action_item.model_dump() if hasattr(action_item, "model_dump") else dict(action_item.__dict__)
        payload["vector"] = embed_text(payload["task"])
        data["action_items"] = [item for item in data["action_items"] if item["id"] != payload["id"]]
        data["action_items"].append(payload)
        self._save(data)

    def upsert_meeting_chunk(self, meeting_chunk: Any) -> None:
        data = self._load()
        payload = meeting_chunk.model_dump() if hasattr(meeting_chunk, "model_dump") else dict(meeting_chunk.__dict__)
        payload["vector"] = embed_text(payload.get("redacted_text") or payload["text"])
        data["meeting_chunks"] = [item for item in data["meeting_chunks"] if item["id"] != payload["id"]]
        data["meeting_chunks"].append(payload)
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

    def list_decisions(self, team_id: str, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        data = self._load()
        results: List[Dict[str, Any]] = []
        for item in data["decisions"]:
            if item.get("team_id") != team_id:
                continue
            if status and item.get("status") != status:
                continue
            payload = dict(item)
            payload.pop("vector", None)
            results.append(payload)
        return sorted(results, key=lambda item: str(item.get("created_at", "")), reverse=True)[:limit]

    def _list_payloads(self, collection: str, team_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        data = self._load()
        results: List[Dict[str, Any]] = []
        for item in data[collection]:
            if item.get("team_id") != team_id:
                continue
            payload = dict(item)
            payload.pop("vector", None)
            results.append(payload)
        return results[:limit]

    def list_action_items(self, team_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self._list_payloads("action_items", team_id, limit)

    def list_meeting_chunks(self, team_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self._list_payloads("meeting_chunks", team_id, limit)


class QdrantVectorMemory:
    """Qdrant-backed implementation of the same memory contract used locally."""

    def __init__(self, url: str, api_key: str = "") -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, PayloadSchemaType, VectorParams
        except Exception as exc:  # pragma: no cover - exercised only without optional dep
            raise RuntimeError("MEMORY_BACKEND=qdrant requires qdrant-client to be installed.") from exc

        self._models = __import__("qdrant_client.models", fromlist=["models"])
        self.client = QdrantClient(url=url, api_key=api_key or None)
        last_error: Optional[Exception] = None
        for collection in (DECISIONS_COLLECTION, ACTION_ITEMS_COLLECTION, MEETING_CHUNKS_COLLECTION):
            for _ in range(12):
                try:
                    if self.client.collection_exists(collection):
                        self._recreate_if_vector_size_mismatch(collection)
                    if not self.client.collection_exists(collection):
                        self.client.create_collection(
                            collection_name=collection,
                            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                        )
                    self._ensure_payload_index(collection, "team_id", PayloadSchemaType.KEYWORD)
                    if collection == DECISIONS_COLLECTION:
                        self._ensure_payload_index(collection, "status", PayloadSchemaType.KEYWORD)
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    time.sleep(1)
            if last_error is not None:
                raise RuntimeError(f"Could not initialize Qdrant collection {collection}: {last_error}") from last_error

    def _recreate_if_vector_size_mismatch(self, collection: str) -> None:
        if os.getenv("QDRANT_RECREATE_ON_VECTOR_SIZE_MISMATCH", "1").lower() not in {"1", "true", "yes"}:
            return
        configured_size = self._collection_vector_size(collection)
        if configured_size is not None and configured_size != VECTOR_SIZE:
            self.client.delete_collection(collection)

    def _collection_vector_size(self, collection: str) -> Optional[int]:
        try:
            info = self.client.get_collection(collection)
            vectors = info.config.params.vectors
            size = getattr(vectors, "size", None)
            if size is not None:
                return int(size)
            if isinstance(vectors, dict):
                first = next(iter(vectors.values()))
                if isinstance(first, dict):
                    return int(first.get("size"))
                first_size = getattr(first, "size", None)
                if first_size is not None:
                    return int(first_size)
        except Exception:
            return None
        return None

    def _ensure_payload_index(self, collection: str, field_name: str, field_schema: Any) -> None:
        try:
            self.client.create_payload_index(
                collection_name=collection,
                field_name=field_name,
                field_schema=field_schema,
            )
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                raise

    @staticmethod
    def _point_id(item_id: str, namespace: str = DECISIONS_COLLECTION) -> str:
        if namespace == DECISIONS_COLLECTION:
            return str(uuid5(NAMESPACE_URL, f"meetingmate:{item_id}"))
        return str(uuid5(NAMESPACE_URL, f"meetingmate:{namespace}:{item_id}"))

    def _with_retry(self, label: str, operation: Any) -> Any:
        attempts = int(os.getenv("QDRANT_RETRY_ATTEMPTS", "3"))
        delay = float(os.getenv("QDRANT_RETRY_DELAY_SECONDS", "0.2"))
        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
                if attempt < attempts - 1:
                    time.sleep(delay * (2 ** attempt))
        raise RuntimeError(f"Qdrant {label} failed after {attempts} attempts: {last_error}") from last_error

    def reset(self) -> None:
        def operation() -> None:
            for collection in (DECISIONS_COLLECTION, ACTION_ITEMS_COLLECTION, MEETING_CHUNKS_COLLECTION):
                if self.client.collection_exists(collection):
                    self.client.delete_collection(collection)

        self._with_retry("reset", operation)
        self.__init__(os.getenv("QDRANT_URL", "http://localhost:6333"), os.getenv("QDRANT_API_KEY", ""))

    def upsert_decision(self, decision: Any) -> None:
        PointStruct = self._models.PointStruct
        payload = decision.model_dump() if hasattr(decision, "model_dump") else dict(decision.__dict__)
        vector = embed_text(payload["text"])
        payload.pop("vector", None)
        self._with_retry(
            "upsert_decision",
            lambda: self.client.upsert(
                collection_name=DECISIONS_COLLECTION,
                points=[PointStruct(id=self._point_id(payload["id"]), vector=vector, payload=payload)],
            ),
        )

    def upsert_action_item(self, action_item: Any) -> None:
        PointStruct = self._models.PointStruct
        payload = action_item.model_dump() if hasattr(action_item, "model_dump") else dict(action_item.__dict__)
        vector = embed_text(payload["task"])
        payload.pop("vector", None)
        self._with_retry(
            "upsert_action_item",
            lambda: self.client.upsert(
                collection_name=ACTION_ITEMS_COLLECTION,
                points=[PointStruct(id=self._point_id(payload["id"], ACTION_ITEMS_COLLECTION), vector=vector, payload=payload)],
            ),
        )

    def upsert_meeting_chunk(self, meeting_chunk: Any) -> None:
        PointStruct = self._models.PointStruct
        payload = meeting_chunk.model_dump() if hasattr(meeting_chunk, "model_dump") else dict(meeting_chunk.__dict__)
        vector = embed_text(payload.get("redacted_text") or payload["text"])
        payload.pop("vector", None)
        self._with_retry(
            "upsert_meeting_chunk",
            lambda: self.client.upsert(
                collection_name=MEETING_CHUNKS_COLLECTION,
                points=[PointStruct(id=self._point_id(payload["id"], MEETING_CHUNKS_COLLECTION), vector=vector, payload=payload)],
            ),
        )

    def update_decision(self, decision_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        point_id = self._point_id(decision_id)
        points = self._with_retry(
            "retrieve_decision",
            lambda: self.client.retrieve(collection_name=DECISIONS_COLLECTION, ids=[point_id], with_payload=True),
        )
        if not points:
            return None
        updated = dict(points[0].payload or {})
        updated.update(fields)
        self._with_retry(
            "update_decision",
            lambda: self.client.set_payload(collection_name=DECISIONS_COLLECTION, payload=fields, points=[point_id]),
        )
        return updated

    def search_decisions(self, query: str, team_id: str, limit: int = 5, status: Optional[str] = None) -> List[Dict[str, Any]]:
        FieldCondition = self._models.FieldCondition
        Filter = self._models.Filter
        MatchValue = self._models.MatchValue
        conditions = [FieldCondition(key="team_id", match=MatchValue(value=team_id))]
        if status:
            conditions.append(FieldCondition(key="status", match=MatchValue(value=status)))
        hits = self._with_retry(
            "search_decisions",
            lambda: self.client.search(
                collection_name=DECISIONS_COLLECTION,
                query_vector=embed_text(query),
                query_filter=Filter(must=conditions),
                limit=limit,
                with_payload=True,
            ),
        )
        results: List[Dict[str, Any]] = []
        for hit in hits:
            payload = dict(hit.payload or {})
            payload["score"] = float(hit.score)
            results.append(payload)
        return results

    def list_decisions(self, team_id: str, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        FieldCondition = self._models.FieldCondition
        Filter = self._models.Filter
        MatchValue = self._models.MatchValue
        conditions = [FieldCondition(key="team_id", match=MatchValue(value=team_id))]
        if status:
            conditions.append(FieldCondition(key="status", match=MatchValue(value=status)))
        points, _ = self._with_retry(
            "list_decisions",
            lambda: self.client.scroll(
                collection_name=DECISIONS_COLLECTION,
                scroll_filter=Filter(must=conditions),
                limit=limit,
                with_payload=True,
            ),
        )
        results = [dict(point.payload or {}) for point in points]
        return sorted(results, key=lambda item: str(item.get("created_at", "")), reverse=True)

    def _list_collection(self, collection: str, team_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        FieldCondition = self._models.FieldCondition
        Filter = self._models.Filter
        MatchValue = self._models.MatchValue
        points, _ = self._with_retry(
            f"list_{collection}",
            lambda: self.client.scroll(
                collection_name=collection,
                scroll_filter=Filter(must=[FieldCondition(key="team_id", match=MatchValue(value=team_id))]),
                limit=limit,
                with_payload=True,
            ),
        )
        return [dict(point.payload or {}) for point in points]

    def list_action_items(self, team_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self._list_collection(ACTION_ITEMS_COLLECTION, team_id, limit)

    def list_meeting_chunks(self, team_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self._list_collection(MEETING_CHUNKS_COLLECTION, team_id, limit)


def get_memory() -> VectorMemory:
    backend = os.getenv("MEMORY_BACKEND", "local").lower()
    if backend == "qdrant":
        return QdrantVectorMemory(os.getenv("QDRANT_URL", "http://localhost:6333"), os.getenv("QDRANT_API_KEY", ""))
    return LocalVectorMemory(os.getenv("LOCAL_MEMORY_PATH", "backend/app/memory/local_ledger.json"))
