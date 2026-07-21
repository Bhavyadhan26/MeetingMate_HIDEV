from __future__ import annotations

from typing import Any, Dict


class AppError(Exception):
    status_code = 500
    code = "application_error"

    def __init__(self, message: str, *, detail: Dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}

    def to_detail(self) -> Dict[str, Any]:
        payload = {"code": self.code, "message": self.message}
        if self.detail:
            payload["detail"] = self.detail
        return payload


class MalformedTranscriptError(AppError):
    status_code = 400
    code = "malformed_transcript"


class DependencyUnavailableError(AppError):
    status_code = 503
    code = "dependency_unavailable"


class ProviderRateLimitedError(AppError):
    status_code = 429
    code = "provider_rate_limited"


def classify_processing_error(exc: Exception, operation: str) -> AppError:
    message = str(exc)
    lowered = message.lower()
    if any(marker in lowered for marker in ("rate limit", "rate-limit", "quota", "429", "too many requests")):
        return ProviderRateLimitedError(
            "The AI provider is rate limited. Retry after the provider quota resets.",
            detail={"operation": operation},
        )
    if any(marker in lowered for marker in ("qdrant", "connection", "refused", "unreachable", "timeout", "timed out")):
        return DependencyUnavailableError(
            "A required backend dependency is unavailable. Retry after the service is healthy.",
            detail={"operation": operation},
        )
    return DependencyUnavailableError(
        "The meeting pipeline could not complete right now. Retry after the service is healthy.",
        detail={"operation": operation},
    )
