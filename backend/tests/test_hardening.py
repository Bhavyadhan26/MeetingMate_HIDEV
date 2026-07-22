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

    def test_audio_upload_rejects_unsupported_file_type(self) -> None:
        if TestClient is None:
            self.skipTest("FastAPI test client is not installed.")
        from backend.app.main import app

        response = TestClient(app).post(
            "/v1/transcripts/upload",
            files={"file": ("meeting.txt", b"not audio", "text/plain")},
            data={"title": "Bad audio", "team_id": "audio-test"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "malformed_transcript")

    def test_audio_upload_queues_deepgram_job(self) -> None:
        if TestClient is None:
            self.skipTest("FastAPI test client is not installed.")
        from backend.app.main import app

        response = TestClient(app).post(
            "/v1/transcripts/upload",
            files={"file": ("meeting.wav", b"RIFF....WAVE", "audio/wav")},
            data={"title": "Audio path", "team_id": "audio-test", "attendees": "Asha Rao", "agenda": "memory"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("job_id", response.json())

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
        from backend.app.api import routes
        from backend.app.memory.vector_store import LocalVectorMemory
        from backend.app.persistence.database import MetadataStore
        from backend.app.agents.recall_agent import RecallAgent
        from backend.app.services import MeetingPipeline

        client = TestClient(app)
        memory_tmp = tempfile.NamedTemporaryFile(delete=False)
        memory_tmp.close()
        os.unlink(memory_tmp.name)
        metadata_tmp = tempfile.NamedTemporaryFile(delete=False)
        metadata_tmp.close()
        os.unlink(metadata_tmp.name)
        final = None
        try:
            test_memory = LocalVectorMemory(memory_tmp.name)
            test_metadata = MetadataStore(sqlite_path=metadata_tmp.name)
            routes._worker_started = False
            with (
                patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=False),
                patch.object(routes, "_memory", test_memory),
                patch.object(routes, "_pipeline", MeetingPipeline(test_memory)),
                patch.object(routes, "_recall", RecallAgent(test_memory)),
                patch.object(routes, "_metadata", test_metadata),
                patch("backend.app.memory.vector_store.embed_text", return_value=[0.1] * 384),
            ):
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

                for _ in range(120):
                    polled = client.get(f"/v1/transcripts/jobs/{job_id}")
                    self.assertEqual(polled.status_code, 200)
                    payload = polled.json()
                    if payload["status"] == "completed":
                        final = payload
                        break
                    time.sleep(0.25)
        finally:
            for path in (memory_tmp.name, metadata_tmp.name):
                if os.path.exists(path):
                    os.unlink(path)

        self.assertIsNotNone(final)
        self.assertEqual(final["result"]["decisions"][0]["text"], "use Qdrant for async job memory")
        self.assertEqual(final["status"], "completed")
        self.assertIsNotNone(final["expires_at"])

    def test_terminal_async_jobs_expire_after_ttl(self) -> None:
        from backend.app.api import routes
        from backend.app.agents.recall_agent import RecallAgent
        from backend.app.memory.vector_store import LocalVectorMemory
        from backend.app.persistence.database import MetadataStore
        from backend.app.services import MeetingPipeline

        expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        stale = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        memory_tmp = tempfile.NamedTemporaryFile(delete=False)
        metadata_tmp = tempfile.NamedTemporaryFile(delete=False)
        memory_tmp.close()
        metadata_tmp.close()
        os.unlink(memory_tmp.name)
        os.unlink(metadata_tmp.name)
        try:
            memory = LocalVectorMemory(memory_tmp.name)
            metadata = MetadataStore(sqlite_path=metadata_tmp.name)
            now = datetime.now(timezone.utc).isoformat()
            for job_id, status, expires_at in (
                ("job-expired", "completed", expired),
                ("job-active", "processing", expired),
                ("job-stale", "failed", stale),
            ):
                metadata.create_job(
                    {"job_id": job_id, "status": status, "created_at": now, "updated_at": now, "expires_at": expires_at},
                    {"transcript": "Decision: keep Qdrant."},
                    "transcript",
                )
                metadata.update_job(job_id, status=status, expires_at=expires_at)

            with (
                patch.object(routes, "_memory", memory),
                patch.object(routes, "_pipeline", MeetingPipeline(memory)),
                patch.object(routes, "_recall", RecallAgent(memory)),
                patch.object(routes, "_metadata", metadata),
                patch.dict(os.environ, {"TRANSCRIPT_JOB_TTL_SECONDS": "1"}, clear=False),
            ):
                self.assertEqual(routes.get_transcript_job("job-expired")["error"], "Job not found")
                self.assertEqual(routes.get_transcript_job("job-active")["status"], "processing")
                self.assertEqual(routes.get_transcript_job("job-stale")["error"], "Job not found")
        finally:
            for path in (memory_tmp.name, metadata_tmp.name):
                if os.path.exists(path):
                    os.unlink(path)

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
            with patch("backend.app.memory.vector_store.embed_text", return_value=[0.1] * 384):
                memory.upsert_decision(decision)
            memory.update_decision(decision.id, created_at=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat())
            with patch.object(routes, "_memory", memory), patch.dict(os.environ, {"CONFLICT_ESCALATION_HOURS": "24"}, clear=False):
                result = routes.list_unresolved_conflicts("audit-team")
            self.assertEqual(len(result["conflicts"]), 1)
            self.assertTrue(result["conflicts"][0]["escalation"]["expired"])
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
