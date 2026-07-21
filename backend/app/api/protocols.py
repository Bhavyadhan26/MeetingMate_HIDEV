from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict
from uuid import uuid4

from backend.app.api import routes


A2A_VERSION = "1.0"
PROTOCOL_VERSION = "0.1.0"
_A2A_TASKS: Dict[str, Dict[str, Any]] = {}


def public_base_url() -> str:
    return os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


def a2a_agent_card(base_url: str | None = None) -> Dict[str, Any]:
    root = (base_url or public_base_url()).rstrip("/")
    return {
        "name": "MeetingMate AI Chief of Staff",
        "description": "Extracts meeting decisions and action items, detects decision drift, resolves conflicts, and recalls cited organizational memory.",
        "provider": {"organization": "MeetingMate", "url": root},
        "version": PROTOCOL_VERSION,
        "supportedInterfaces": [
            {
                "url": f"{root}/v1/a2a",
                "protocolBinding": "JSON-RPC",
                "protocolVersion": A2A_VERSION,
            }
        ],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": "transcript-ingest",
                "name": "Meeting Transcript Ingestion",
                "description": "Process a transcript through the ADK extraction swarm and persist grounded decisions, action items, and meeting chunks.",
                "tags": ["meetings", "ingestion", "adk", "qdrant"],
                "examples": ["Process this transcript and detect decision drift."],
            },
            {
                "id": "meeting-memory-recall",
                "name": "Cited Meeting Memory Recall",
                "description": "Answer natural-language questions using cited decisions retrieved from MeetingMate memory.",
                "tags": ["memory", "rag", "qdrant", "citations"],
                "examples": ["What did we decide about Qdrant?"],
            },
            {
                "id": "pre-meeting-brief",
                "name": "Pre-Meeting Brief",
                "description": "Generate agenda-specific briefs with citations to prior decisions.",
                "tags": ["brief", "agenda", "recall"],
                "examples": ["Prepare a brief for Qdrant ledger planning."],
            },
            {
                "id": "conflict-resolution",
                "name": "Decision Conflict Resolution",
                "description": "List and resolve conflicted decisions through the human-in-the-loop resolution path.",
                "tags": ["decision-drift", "conflicts", "hitl"],
                "examples": ["List unresolved conflicts for the platform team."],
            },
        ],
        "securitySchemes": {},
        "security": [],
    }


def handle_a2a_jsonrpc(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _jsonrpc_dispatch(payload, _A2A_METHODS)


def handle_mcp_jsonrpc(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _jsonrpc_dispatch(payload, _MCP_METHODS)


def _jsonrpc_dispatch(payload: Dict[str, Any], methods: Dict[str, Callable[[Dict[str, Any]], Any]]) -> Dict[str, Any]:
    request_id = payload.get("id")
    method = payload.get("method")
    if not isinstance(method, str):
        return _jsonrpc_error(request_id, -32600, "Invalid Request", "method must be a string")
    handler = methods.get(method)
    if handler is None:
        return _jsonrpc_error(request_id, -32601, "Method not found", method)
    params = payload.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return _jsonrpc_error(request_id, -32602, "Invalid params", "params must be an object")
    try:
        result = handler(params)
    except Exception as exc:
        return _jsonrpc_error(request_id, -32000, "Server error", str(exc))
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str, detail: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message, "data": detail}}


def _a2a_send_message(params: Dict[str, Any]) -> Dict[str, Any]:
    metadata = params.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    skill = metadata.get("skill") or metadata.get("skill_id") or "meeting-memory-recall"
    text = _extract_message_text(params.get("message", {}))
    team_id = str(metadata.get("team_id", "demo-team"))
    if skill == "transcript-ingest":
        transcript_payload = metadata.get("transcript_payload")
        if not isinstance(transcript_payload, dict):
            transcript_payload = {"title": metadata.get("title", "A2A transcript"), "team_id": team_id, "transcript": text}
        result = routes.process_transcript(transcript_payload)
    elif skill == "pre-meeting-brief":
        agenda = metadata.get("agenda") or [line.strip() for line in text.splitlines() if line.strip()]
        result = routes.pre_meeting_brief({"team_id": team_id, "agenda": agenda})
    elif skill == "conflict-resolution":
        result = routes.list_unresolved_conflicts(team_id)
    else:
        result = routes.search_memory(text, team_id)
    task = _completed_a2a_task(skill=str(skill), request_text=text, result=result)
    _A2A_TASKS[task["id"]] = task
    return task


def _a2a_get_task(params: Dict[str, Any]) -> Dict[str, Any]:
    task_id = str(params.get("taskId") or params.get("id") or "")
    task = _A2A_TASKS.get(task_id)
    if not task:
        raise ValueError(f"task {task_id!r} not found")
    return task


def _a2a_cancel_task(params: Dict[str, Any]) -> Dict[str, Any]:
    task_id = str(params.get("taskId") or params.get("id") or "")
    task = _A2A_TASKS.get(task_id)
    if not task:
        raise ValueError(f"task {task_id!r} not found")
    task["status"] = {"state": "canceled", "timestamp": _now()}
    return task


def _completed_a2a_task(skill: str, request_text: str, result: Dict[str, Any]) -> Dict[str, Any]:
    task_id = f"a2a-task-{uuid4().hex[:12]}"
    return {
        "id": task_id,
        "contextId": f"meetingmate-{uuid4().hex[:10]}",
        "status": {"state": "completed", "timestamp": _now()},
        "history": [
            {
                "role": "user",
                "parts": [{"text": request_text}],
            }
        ],
        "artifacts": [
            {
                "artifactId": f"artifact-{uuid4().hex[:12]}",
                "name": skill,
                "parts": [{"data": result}],
            }
        ],
        "metadata": {"skill": skill, "service": "meetingmate"},
    }


def _extract_message_text(message: Any) -> str:
    if isinstance(message, str):
        return message
    if not isinstance(message, dict):
        return ""
    if isinstance(message.get("text"), str):
        return message["text"]
    parts = message.get("parts", [])
    texts: list[str] = []
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    texts.append(part["text"])
                elif isinstance(part.get("text"), dict) and isinstance(part["text"].get("text"), str):
                    texts.append(part["text"]["text"])
    return "\n".join(texts).strip()


def _mcp_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "protocolVersion": params.get("protocolVersion", "2025-06-18"),
        "serverInfo": {"name": "meetingmate", "version": PROTOCOL_VERSION},
        "capabilities": {"tools": {}},
    }


def _mcp_tools_list(params: Dict[str, Any]) -> Dict[str, Any]:
    return {"tools": _MCP_TOOLS}


def _mcp_tools_call(params: Dict[str, Any]) -> Dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    if name == "ingest_transcript":
        result = routes.process_transcript(arguments)
    elif name == "search_memory":
        result = routes.search_memory(str(arguments.get("query", "")), str(arguments.get("team_id", "demo-team")))
    elif name == "pre_meeting_brief":
        result = routes.pre_meeting_brief(arguments)
    elif name == "list_conflicts":
        result = routes.list_unresolved_conflicts(str(arguments.get("team_id", "demo-team")))
    else:
        raise ValueError(f"unknown tool {name!r}")
    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}], "isError": False}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_A2A_METHODS: Dict[str, Callable[[Dict[str, Any]], Any]] = {
    "message/send": _a2a_send_message,
    "tasks/get": _a2a_get_task,
    "tasks/cancel": _a2a_cancel_task,
}

_MCP_METHODS: Dict[str, Callable[[Dict[str, Any]], Any]] = {
    "initialize": _mcp_initialize,
    "tools/list": _mcp_tools_list,
    "tools/call": _mcp_tools_call,
}

_MCP_TOOLS = [
    {
        "name": "ingest_transcript",
        "description": "Run a transcript through MeetingMate's ADK extraction swarm and Qdrant-backed memory pipeline.",
        "inputSchema": {
            "type": "object",
            "required": ["transcript"],
            "properties": {
                "title": {"type": "string"},
                "team_id": {"type": "string"},
                "transcript": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
                "agenda": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "search_memory",
        "description": "Search cited MeetingMate decision memory for a natural-language query.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}, "team_id": {"type": "string"}},
        },
    },
    {
        "name": "pre_meeting_brief",
        "description": "Generate a cited brief for agenda topics.",
        "inputSchema": {
            "type": "object",
            "required": ["agenda"],
            "properties": {
                "team_id": {"type": "string"},
                "agenda": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "list_conflicts",
        "description": "List unresolved decision drift conflicts for a team.",
        "inputSchema": {
            "type": "object",
            "properties": {"team_id": {"type": "string"}},
        },
    },
]
