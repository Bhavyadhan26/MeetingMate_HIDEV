import os
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from backend.app.memory.vector_store import QdrantVectorMemory
from backend.app.services.errors import (
    DependencyUnavailableError,
    ProviderRateLimitedError,
    classify_processing_error,
)


class HardeningTests(unittest.TestCase):
    def test_malformed_transcript_returns_structured_400(self) -> None:
        if TestClient is None:
            self.skipTest("FastAPI test client is not installed.")
        from backend.app.main import app

        response = TestClient(app).post("/v1/transcripts", json={"transcript": 42})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "malformed_transcript")

    def test_dependency_error_returns_structured_503(self) -> None:
        if TestClient is None:
            self.skipTest("FastAPI test client is not installed.")
        from backend.app.main import app

        with patch("backend.app.main.search_memory", side_effect=DependencyUnavailableError("Qdrant is unreachable")):
            response = TestClient(app).get("/v1/memory/search?query=qdrant&team_id=platform")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "dependency_unavailable")

    def test_rate_limit_exception_is_classified(self) -> None:
        error = classify_processing_error(RuntimeError("429 rate limit from model provider"), "transcript_ingest")
        self.assertIsInstance(error, ProviderRateLimitedError)
        self.assertEqual(error.status_code, 429)

    def test_qdrant_retry_succeeds_after_transient_failures(self) -> None:
        memory = QdrantVectorMemory.__new__(QdrantVectorMemory)
        calls = {"count": 0}

        def operation() -> str:
            calls["count"] += 1
            if calls["count"] < 3:
                raise RuntimeError("temporary connection refused")
            return "ok"

        with patch.dict(os.environ, {"QDRANT_RETRY_ATTEMPTS": "3", "QDRANT_RETRY_DELAY_SECONDS": "0"}, clear=False):
            self.assertEqual(memory._with_retry("unit_test", operation), "ok")
        self.assertEqual(calls["count"], 3)


if __name__ == "__main__":
    unittest.main()
