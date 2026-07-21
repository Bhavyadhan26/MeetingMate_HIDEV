from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ADKRuntimeStatus:
    available: bool
    detail: str
    version: Optional[str] = None


def detect_adk_runtime() -> ADKRuntimeStatus:
    """Detect Google ADK without making local tests depend on it."""
    try:
        import importlib.metadata

        version = importlib.metadata.version("google-adk")
        __import__("google.adk")
        return ADKRuntimeStatus(True, "google.adk import succeeded", version)
    except Exception as exc:  # pragma: no cover - depends on optional runtime
        return ADKRuntimeStatus(False, f"Google ADK unavailable: {exc}")
