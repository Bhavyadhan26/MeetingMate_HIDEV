import os
import tempfile
import unittest

from backend.app.memory.vector_store import LocalVectorMemory
from backend.app.models import Decision


class SemanticMemoryTests(unittest.TestCase):
    def test_minilm_ranks_semantically_closest_decision_first(self) -> None:
        try:
            import sentence_transformers  # noqa: F401
        except Exception:
            self.skipTest("sentence-transformers is not installed.")

        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        os.unlink(tmp.name)
        try:
            memory = LocalVectorMemory(tmp.name)
            samples = [
                Decision(
                    meeting_id="meeting-1",
                    team_id="semantic-test",
                    text="use Qdrant for semantic vector memory and recall search",
                    source_excerpt="Decision: use Qdrant for semantic vector memory and recall search.",
                ),
                Decision(
                    meeting_id="meeting-2",
                    team_id="semantic-test",
                    text="launch the beta onboarding program next Friday",
                    source_excerpt="Decision: launch the beta onboarding program next Friday.",
                ),
                Decision(
                    meeting_id="meeting-3",
                    team_id="semantic-test",
                    text="route billing invoices through Stripe exports",
                    source_excerpt="Decision: route billing invoices through Stripe exports.",
                ),
            ]
            for decision in samples:
                memory.upsert_decision(decision)

            results = memory.search_decisions("Which vector database powers memory recall?", "semantic-test", limit=3)
            self.assertEqual(results[0]["id"], samples[0].id)
            self.assertGreater(results[0]["score"], results[1]["score"])
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
