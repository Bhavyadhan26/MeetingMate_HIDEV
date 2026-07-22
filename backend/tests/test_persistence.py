import os
import tempfile
import unittest

from backend.app.persistence.database import MetadataStore


class PersistenceTests(unittest.TestCase):
    def test_sqlite_store_persists_meeting_redaction_and_jobs(self) -> None:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        os.unlink(tmp.name)
        try:
            store = MetadataStore(sqlite_path=tmp.name)
            store.save_meeting(
                {
                    "id": "meeting-1",
                    "team_id": "platform",
                    "title": "Planning",
                    "attendees": ["Asha Rao"],
                    "agenda": ["memory"],
                    "created_at": "2026-07-22T00:00:00+00:00",
                }
            )
            store.save_redaction_map("meeting-1", "platform", {"Asha Rao": "[PERSON_1]"})
            store.create_job(
                {
                    "job_id": "job-1",
                    "status": "queued",
                    "created_at": "2026-07-22T00:00:00+00:00",
                    "updated_at": "2026-07-22T00:00:00+00:00",
                    "expires_at": None,
                },
                {"transcript": "Decision: use Qdrant."},
                "transcript",
            )
            store.update_job("job-1", status="completed", result={"ok": True}, expires_at="2099-01-01T00:00:00+00:00")

            reopened = MetadataStore(sqlite_path=tmp.name)
            job = reopened.get_job("job-1")
            self.assertEqual(job["status"], "completed")
            self.assertEqual(job["payload"]["transcript"], "Decision: use Qdrant.")
            self.assertEqual(job["result"], {"ok": True})
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
