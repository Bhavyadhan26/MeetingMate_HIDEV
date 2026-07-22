from __future__ import annotations

from functools import lru_cache
from typing import List

DIMENSIONS = 384
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def embed_text(text: str) -> List[float]:
    vector = _model().encode(text or "", normalize_embeddings=True)
    return [float(value) for value in vector.tolist()]


@lru_cache(maxsize=1)
def _model() -> object:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def cosine(left: List[float], right: List[float]) -> float:
    return sum(a * b for a, b in zip(left, right))
