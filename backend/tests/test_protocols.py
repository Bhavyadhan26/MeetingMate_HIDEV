import json
import unittest
from unittest.mock import patch

from backend.app.api import protocols


class ProtocolSurfaceTests(unittest.TestCase):
    def test_a2a_agent_card_declares_discovery_and_skills(self) -> None:
        card = protocols.a2a_agent_card("http://testserver")

        self.assertEqual(card["name"], "MeetingMate AI Chief of Staff")
        self.assertEqual(card["supportedInterfaces"][0]["url"], "http://testserver/v1/a2a")
        self.assertEqual(card["supportedInterfaces"][0]["protocolBinding"], "JSON-RPC")
        skill_ids = {skill["id"] for skill in card["skills"]}
        self.assertIn("transcript-ingest", skill_ids)
        self.assertIn("meeting-memory-recall", skill_ids)
        self.assertIn("pre-meeting-brief", skill_ids)

    def test_mcp_lists_real_meetingmate_tools(self) -> None:
        response = protocols.handle_mcp_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

        self.assertEqual(response["id"], 1)
        tool_names = {tool["name"] for tool in response["result"]["tools"]}
        self.assertEqual({"ingest_transcript", "search_memory", "pre_meeting_brief", "list_conflicts"}, tool_names)

    def test_mcp_tool_call_routes_to_recall_service(self) -> None:
        with patch.object(protocols.routes, "search_memory", return_value={"answer": "Most relevant decision", "citations": []}) as search:
            response = protocols.handle_mcp_jsonrpc(
                {
                    "jsonrpc": "2.0",
                    "id": "call-1",
                    "method": "tools/call",
                    "params": {"name": "search_memory", "arguments": {"query": "What did we decide?", "team_id": "platform"}},
                }
            )

        search.assert_called_once_with("What did we decide?", "platform")
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(content["answer"], "Most relevant decision")

    def test_a2a_message_send_returns_completed_task_and_tasks_get(self) -> None:
        with patch.object(protocols.routes, "search_memory", return_value={"answer": "Qdrant was selected.", "citations": []}) as search:
            sent = protocols.handle_a2a_jsonrpc(
                {
                    "jsonrpc": "2.0",
                    "id": "a2a-1",
                    "method": "message/send",
                    "params": {
                        "message": {"role": "user", "parts": [{"text": "What did we decide about Qdrant?"}]},
                        "metadata": {"team_id": "platform", "skill": "meeting-memory-recall"},
                    },
                }
            )

        search.assert_called_once_with("What did we decide about Qdrant?", "platform")
        task = sent["result"]
        self.assertEqual(task["status"]["state"], "completed")
        self.assertEqual(task["metadata"]["skill"], "meeting-memory-recall")

        fetched = protocols.handle_a2a_jsonrpc(
            {"jsonrpc": "2.0", "id": "a2a-2", "method": "tasks/get", "params": {"taskId": task["id"]}}
        )
        self.assertEqual(fetched["result"]["id"], task["id"])

    def test_jsonrpc_unknown_method_returns_error(self) -> None:
        response = protocols.handle_mcp_jsonrpc({"jsonrpc": "2.0", "id": 3, "method": "missing/method"})

        self.assertEqual(response["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
