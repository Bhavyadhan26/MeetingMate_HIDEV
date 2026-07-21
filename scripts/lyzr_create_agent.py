from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENT_BASE_URL = "https://agent-prod.studio.lyzr.ai"


def main() -> int:
    load_dotenv(ROOT / ".env")
    try:
        result = create_lyzr_agent()
    except RuntimeError as exc:
        print(json.dumps({"lyzr_create_agent": "failed", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def create_lyzr_agent() -> dict[str, Any]:
    api_key = os.getenv("LYZR_API_KEY", "").strip()
    base_url = os.getenv("LYZR_AGENT_BASE_URL", DEFAULT_AGENT_BASE_URL).strip().rstrip("/")
    dry_run = os.getenv("LYZR_CREATE_AGENT_DRY_RUN", "").lower() in {"1", "true", "yes"}
    if not api_key:
        raise RuntimeError("Set LYZR_API_KEY before creating a Lyzr agent.")
    payload = build_agent_payload()
    if dry_run:
        return {
            "lyzr_create_agent": "dry_run",
            "payload": redact_payload(payload),
            "next_step": "Unset LYZR_CREATE_AGENT_DRY_RUN to create the agent, then set LYZR_AGENT_ID from the response.",
        }
    response = request_json(f"{base_url}/v3/agents/", api_key, payload)
    agent_id = response.get("agent_id") or response.get("id")
    if not agent_id:
        raise RuntimeError(f"Lyzr create agent returned no agent id: {response}")
    return {
        "lyzr_create_agent": "created",
        "agent_id": agent_id,
        "name": payload["name"],
        "response": response,
        "next_step": "Set LYZR_AGENT_ID to this value and run scripts/lyzr_agent_check.py.",
    }


def build_agent_payload() -> dict[str, Any]:
    rag_id = os.getenv("LYZR_RAG_ID", "").strip()
    public_base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    features = parse_json_env("LYZR_AGENT_FEATURES_JSON", [])
    if rag_id and os.getenv("LYZR_AGENT_INCLUDE_KB_FEATURE", "").lower() in {"1", "true", "yes"}:
        features.append(
            {
                "type": "KNOWLEDGE_BASE",
                "config": {
                    "lyzr_rag": {},
                    "agentic_rag": [
                        {
                            "rag_id": rag_id,
                            "top_k": int(os.getenv("LYZR_AGENT_KB_TOP_K", "5")),
                            "retrieval_type": os.getenv("LYZR_AGENT_KB_RETRIEVAL_TYPE", "basic"),
                            "score_threshold": float(os.getenv("LYZR_AGENT_KB_SCORE_THRESHOLD", "0")),
                        }
                    ],
                },
                "priority": 0,
            }
        )
    a2a_tools = parse_json_env("LYZR_AGENT_A2A_TOOLS_JSON", [])
    if public_base_url and os.getenv("LYZR_AGENT_INCLUDE_A2A_TOOL", "").lower() in {"1", "true", "yes"}:
        a2a_tools.append({"base_url": public_base_url})
    return {
        "name": os.getenv("LYZR_AGENT_NAME", "MeetingMate Chief of Staff").strip(),
        "description": os.getenv(
            "LYZR_AGENT_DESCRIPTION",
            "Answers questions about MeetingMate decisions and can orchestrate MeetingMate through A2A when configured.",
        ).strip(),
        "agent_role": os.getenv(
            "LYZR_AGENT_ROLE",
            "You are a meeting intelligence chief of staff for organizational decision memory.",
        ).strip(),
        "agent_instructions": os.getenv(
            "LYZR_AGENT_INSTRUCTIONS",
            "Answer using MeetingMate decision memory. Prefer cited, concise answers. If tools are available, use them to retrieve current decisions.",
        ).strip(),
        "agent_goal": os.getenv("LYZR_AGENT_GOAL", "Help teams recall decisions and identify decision drift.").strip(),
        "agent_context": os.getenv(
            "LYZR_AGENT_CONTEXT",
            "MeetingMate stores decisions, action items, and meeting chunks in Qdrant and exposes MCP/A2A protocol surfaces.",
        ).strip(),
        "agent_output": os.getenv("LYZR_AGENT_OUTPUT", "Concise answer with cited decision details when available.").strip(),
        "examples": os.getenv("LYZR_AGENT_EXAMPLES", "User: What did we decide about Qdrant?\nAgent: We decided to use Qdrant as the persistent vector ledger, citing the stored decision excerpt.").strip(),
        "features": features,
        "tools": parse_json_env("LYZR_AGENT_TOOLS_JSON", []),
        "tool_usage_description": os.getenv("LYZR_AGENT_TOOL_USAGE", "Use configured tools only when they improve factual recall.").strip(),
        "llm_credential_id": os.getenv("LYZR_LLM_CREDENTIAL_ID", "lyzr_openai").strip(),
        "response_format": parse_json_env("LYZR_AGENT_RESPONSE_FORMAT_JSON", {}),
        "provider_id": os.getenv("LYZR_AGENT_PROVIDER_ID", "openai").strip(),
        "model": os.getenv("LYZR_AGENT_MODEL", "gpt-4o-mini").strip(),
        "top_p": float(os.getenv("LYZR_AGENT_TOP_P", "1")),
        "temperature": float(os.getenv("LYZR_AGENT_TEMPERATURE", "0.2")),
        "managed_agents": parse_json_env("LYZR_AGENT_MANAGED_AGENTS_JSON", []),
        "tool_configs": parse_json_env("LYZR_AGENT_TOOL_CONFIGS_JSON", []),
        "store_messages": True,
        "file_output": False,
        "a2a_tools": a2a_tools,
        "voice_config": {},
        "additional_model_params": parse_json_env("LYZR_AGENT_ADDITIONAL_MODEL_PARAMS_JSON", {}),
        "max_iterations": int(os.getenv("LYZR_AGENT_MAX_ITERATIONS", "10")),
        "git_agent": {"enabled": False},
        "proxy_config": {"enabled": False, "passthrough_tools": True, "passthrough_tool_choice": True, "passthrough_response_format": True},
    }


def parse_json_env(key: str, default: Any) -> Any:
    raw = os.getenv(key, "").strip()
    if not raw:
        return list(default) if isinstance(default, list) else dict(default) if isinstance(default, dict) else default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{key} must be valid JSON.") from exc


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(payload)
    for key in ("llm_credential_id",):
        if redacted.get(key):
            redacted[key] = "<configured>"
    return redacted


def request_json(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"accept": "application/json", "content-type": "application/json", "x-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read(800).decode("utf-8", errors="replace")
        raise RuntimeError(f"Lyzr create agent API returned status={exc.code} response={detail!r}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Lyzr create agent API request failed: {exc}") from exc
    try:
        data = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Lyzr create agent API returned non-JSON response: {response_body[:300]!r}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Lyzr create agent API returned an unexpected non-object response.")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
