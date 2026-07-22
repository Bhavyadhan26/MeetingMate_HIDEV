import os
import tempfile
import unittest

from backend.app.agents.recall_agent import RecallAgent
from backend.app.memory import LocalVectorMemory
from backend.app.services.pipeline import MeetingPipeline
from backend.app.services.redaction import redact_pii


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        os.unlink(self.tmp.name)
        self.memory = LocalVectorMemory(self.tmp.name)
        self.pipeline = MeetingPipeline(self.memory)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_redaction_uses_stable_placeholders(self) -> None:
        redacted, mapping = redact_pii("Asha Rao emailed asha@example.com. Asha Rao will call +1 415 555 1212.", ["Asha Rao"])
        self.assertNotIn("asha@example.com", redacted)
        self.assertNotIn("+1 415 555 1212", redacted)
        self.assertEqual(redacted.count(mapping["Asha Rao"]), 2)

    def test_redaction_maps_first_name_alias_to_same_placeholder(self) -> None:
        redacted, mapping = redact_pii("Marco Lee joined. Marco will prepare the checklist.", ["Marco Lee"])
        self.assertNotIn("Marco", redacted)
        self.assertNotIn("Marco Lee", redacted)
        self.assertEqual(mapping["Marco Lee"], mapping["Marco"])
        self.assertEqual(mapping["Marco Lee"], "[PERSON_1]")
        self.assertEqual(redacted.count(mapping["Marco Lee"]), 2)

    def test_pipeline_flags_second_meeting_conflict(self) -> None:
        first = self.pipeline.process(
            "Architecture sync",
            "platform",
            "Asha Rao: We decided use Qdrant as the vector ledger. Ravi will document schema by Friday.",
            attendees=["Asha Rao", "Ravi Shah"],
        )
        self.assertEqual(first.decisions[0].status.value if hasattr(first.decisions[0].status, "value") else first.decisions[0].status, "active")
        self.assertIn("Qdrant", first.decisions[0].source_excerpt)

        second = self.pipeline.process(
            "Reversal sync",
            "platform",
            "Decision: no longer use Qdrant as the vector ledger.",
            attendees=["Asha Rao"],
        )
        label = second.decisions[0].drift.label.value if hasattr(second.decisions[0].drift.label, "value") else second.decisions[0].drift.label
        status = second.decisions[0].status.value if hasattr(second.decisions[0].status, "value") else second.decisions[0].status
        self.assertEqual(label, "Potential Conflict")
        self.assertEqual(status, "conflicted")
        self.assertTrue(second.decisions[0].drift.prior_decision_id)

    def test_acknowledged_replacement_supersedes_prior_decision(self) -> None:
        first = self.pipeline.process(
            "Architecture sync",
            "platform",
            "Decision: use Qdrant as the vector ledger.",
            attendees=[],
        )
        prior_id = first.decisions[0].id

        second = self.pipeline.process(
            "Architecture replacement",
            "platform",
            "Decision: replace the prior Qdrant vector ledger decision and use Postgres as the vector ledger.",
            attendees=[],
        )

        new_status = second.decisions[0].status.value if hasattr(second.decisions[0].status, "value") else second.decisions[0].status
        prior = [item for item in self.memory.list_decisions("platform", status="superseded") if item["id"] == prior_id]
        self.assertEqual(new_status, "active")
        self.assertEqual(len(prior), 1)
        self.assertEqual(prior[0]["status"], "superseded")

    def test_pipeline_persists_actions_and_meeting_chunks(self) -> None:
        result = self.pipeline.process(
            "Delivery sync",
            "delivery",
            "Asha Rao: We decided use Qdrant as the vector ledger. Ravi will document schema by Friday.",
            attendees=["Asha Rao", "Ravi Shah"],
        )

        actions = self.memory.list_action_items("delivery")
        chunks = self.memory.list_meeting_chunks("delivery")

        self.assertEqual(len(result.action_items), 1)
        self.assertEqual(actions[0]["id"], result.action_items[0].id)
        self.assertIn("schema", actions[0]["task"].lower())
        self.assertEqual(len(result.meeting_chunks), 1)
        self.assertEqual(chunks[0]["id"], result.meeting_chunks[0].id)
        self.assertIn("[PERSON_1]", chunks[0]["redacted_text"])

    def test_recall_returns_cited_answer(self) -> None:
        self.pipeline.process("Product sync", "product", "We agreed launch beta in September.", attendees=[])
        answer = RecallAgent(self.memory).answer("What did we decide about beta launch?", "product", "trace-test")
        self.assertIn("beta", answer["answer"].lower())
        self.assertGreaterEqual(len(answer["citations"]), 1)
        self.assertIn("source_excerpt", answer["citations"][0])

    def test_pre_meeting_brief_returns_agenda_citations(self) -> None:
        self.pipeline.process("Architecture sync", "platform", "We decided use Qdrant as the vector ledger.", attendees=[])
        brief = RecallAgent(self.memory).pre_meeting_brief(["Qdrant ledger", ""], "platform", "trace-brief-test")
        self.assertEqual(brief.team_id, "platform")
        self.assertEqual(brief.agenda, ["Qdrant ledger"])
        self.assertEqual(len(brief.topics), 1)
        self.assertGreaterEqual(len(brief.topics[0].citations), 1)
        self.assertIn("Qdrant", brief.topics[0].citations[0].source_excerpt)


if __name__ == "__main__":
    unittest.main()
