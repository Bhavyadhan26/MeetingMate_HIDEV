from __future__ import annotations

import hashlib
import math
import re
from typing import List

DIMENSIONS = 64
STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "by",
    "decision",
    "decided",
    "for",
    "in",
    "on",
    "the",
    "to",
    "use",
    "we",
    "agreed",
}


def embed_text(text: str) -> List[float]:
    vector = [0.0] * DIMENSIONS
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if token in STOPWORDS:
            continue
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = digest[0] % DIMENSIONS
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine(left: List[float], right: List[float]) -> float:
    return sum(a * b for a, b in zip(left, right))
