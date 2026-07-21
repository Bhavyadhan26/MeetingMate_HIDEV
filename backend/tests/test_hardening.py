import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from backend.app.memory.vector_store import QdrantVectorMemory
from backend.app.models import Decision
from backend.app.services.errors import (
    AuthorizationError,
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

    def test_async_transcript_job_completes_with_pollable_result(self) -> None:
        if TestClient is None:
            self.skipTest("FastAPI test client is not installed.")
        from backend.app.main import app

        client = TestClient(app)
        response = client.post(
            "/v1/transcripts/async",
            json={
                "title": "Async path",
                "team_id": "async-test",
                "transcript": "We decided use Qdrant for async job memory.",
                "attendees": [],
            },
        )
        self.assertEqual(response.status_code, 200)
        job_id = response.json()["job_id"]

        final = None
        for _ in range(120):
            polled = client.get(f"/v1/transcripts/jobs/{job_id}")
            self.assertEqual(polled.status_code, 200)
            payload = polled.json()
            if payload["status"] == "completed":
                final = payload
                break
            time.sleep(0.25)

        self.assertIsNotNone(final)
        self.assertEqual(final["result"]["decisions"][0]["text"], "use Qdrant for async job memory")
        self.assertEqual(final["status"], "completed")
        self.assertIsNotNone(final["expires_at"])

    def test_terminal_async_jobs_expire_after_ttl(self) -> None:
        from backend.app.api import routes

        expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        stale = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        try:
            routes._jobs["job-expired"] = {"job_id": "job-expired", "status": "completed", "expires_at": expired}
            routes._jobs["job-active"] = {"job_id": "job-active", "status": "processing", "expires_at": expired}
            routes._jobs["job-stale"] = {"job_id": "job-stale", "status": "failed", "expires_at": stale}

            with patch.dict(os.environ, {"TRANSCRIPT_JOB_TTL_SECONDS": "1"}, clear=False):
                self.assertEqual(routes.get_transcript_job("job-expired")["error"], "Job not found")
            self.assertIn("job-active", routes._jobs)
            self.assertEqual(routes.get_transcript_job("job-stale")["error"], "Job not found")
        finally:
            for job_id in ("job-expired", "job-active", "job-stale"):
                routes._jobs.pop(job_id, None)

    def test_invalid_async_job_ttl_falls_back_to_default(self) -> None:
        from backend.app.api import routes

        with patch.dict(os.environ, {"TRANSCRIPT_JOB_TTL_SECONDS": "invalid"}, clear=False):
            self.assertEqual(routes._job_ttl_seconds(), 3600)

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

    def test_qdrant_payload_index_helper_is_idempotent(self) -> None:
        class Client:
            def create_payload_index(self, **_: str) -> None:
                raise RuntimeError("payload index already exists")

        memory = QdrantVectorMemory.__new__(QdrantVectorMemory)
        memory.client = Client()
        memory._ensure_payload_index("decisions", "team_id", "keyword")

    def test_qdrant_payload_index_helper_raises_real_errors(self) -> None:
        class Client:
            def create_payload_index(self, **_: str) -> None:
                raise RuntimeError("permission denied")

        memory = QdrantVectorMemory.__new__(QdrantVectorMemory)
        memory.client = Client()
        with self.assertRaisesRegex(RuntimeError, "permission denied"):
            memory._ensure_payload_index("decisions", "team_id", "keyword")

    def test_resolution_rejects_unprivileged_role(self) -> None:
        from backend.app.api.routes import resolve_decision_with_role

        with self.assertRaises(AuthorizationError):
            resolve_decision_with_role("decision-1", "Observer", "Not authorized.", "observer")

    def test_conflict_audit_marks_expired_unresolved_conflict(self) -> None:
        from backend.app.api import routes
        from backend.app.memory.vector_store import LocalVectorMemory

        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        os.unlink(tmp.name)
        try:
            memory = LocalVectorMemory(tmp.name)
            decision = Decision(
                meeting_id="meeting-old-conflict",
                team_id="audit-team",
                text="no longer use Qdrant",
                source_excerpt="Decision: no longer use Qdrant.",
                status="conflicted",
            )
            memory.upsert_decision(decision)
            memory.update_decision(decision.id, created_at=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat())
            with patch.object(routes, "memory", memory), patch.dict(os.environ, {"CONFLICT_ESCALATION_HOURS": "24"}, clear=False):
                result = routes.list_unresolved_conflicts("audit-team")
            self.assertEqual(len(result["conflicts"]), 1)
            self.assertTrue(result["conflicts"][0]["escalation"]["expired"])
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
