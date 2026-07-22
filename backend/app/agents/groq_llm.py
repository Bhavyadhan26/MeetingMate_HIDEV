from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any


DEFAULT_MODEL = "llama-3.1-8b-instant"


def groq_enabled() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def chat_json(system: str, user: str, *, temperature: float = 0.1, max_tokens: int = 1200) -> dict[str, Any]:
    content = chat_text(system, user, temperature=temperature, max_tokens=max_tokens, json_mode=True)
    return extract_json_object(content)


def chat_text(system: str, user: str, *, temperature: float = 0.1, max_tokens: int = 1200, json_mode: bool = False) -> str:
    if not groq_enabled():
        raise RuntimeError("GROQ_API_KEY is not configured.")
    kwargs: dict[str, Any] = {
        "model": os.getenv("GROQ_MODEL", DEFAULT_MODEL),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = _client().chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def extract_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise RuntimeError("Groq returned an empty response.")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise RuntimeError("Groq JSON response must be an object.")
    return parsed


@lru_cache(maxsize=1)
def _client() -> Any:
    from groq import Groq

    return Groq(api_key=os.getenv("GROQ_API_KEY"))
