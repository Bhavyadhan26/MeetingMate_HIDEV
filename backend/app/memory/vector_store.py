from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .embeddings import cosine, embed_text


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


def get_memory() -> LocalVectorMemory:
    return LocalVectorMemory(os.getenv("LOCAL_MEMORY_PATH", "backend/app/memory/local_ledger.json"))
