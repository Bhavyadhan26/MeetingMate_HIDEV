from __future__ import annotations

import json
import os
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENT_BASE_URL = "https://agent-prod.studio.lyzr.ai"
DEFAULT_MESSAGE = "What did we decide about Qdrant? Include cited decision details if available."


def main() -> int:
    load_dotenv(ROOT / ".env")
    try:
        result = invoke_lyzr_agent()
    except RuntimeError as exc:
        print(json.dumps({"lyzr_agent_check": "failed", "error": str(exc)}, indent=2))
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


def invoke_lyzr_agent() -> dict[str, Any]:
    api_key = os.getenv("LYZR_API_KEY", "").strip()
    agent_id = os.getenv("LYZR_AGENT_ID", "").strip()
    user_id = os.getenv("LYZR_USER_ID", "meetingmate-local@meetingmate.local").strip()
    message = os.getenv("LYZR_AGENT_MESSAGE", DEFAULT_MESSAGE).strip()
    base_url = os.getenv("LYZR_AGENT_BASE_URL", DEFAULT_AGENT_BASE_URL).strip().rstrip("/")
    if not api_key:
        raise RuntimeError("Set LYZR_API_KEY before running the Lyzr agent check.")
    if not agent_id:
        raise RuntimeError(
            "Set LYZR_AGENT_ID to a Lyzr Studio agent that has the MeetingMate Qdrant Knowledge Base attached."
        )
    if not message:
        raise RuntimeError("Set LYZR_AGENT_MESSAGE or use the default non-empty Lyzr agent check query.")
    session_id = os.getenv("LYZR_AGENT_SESSION_ID", f"meetingmate-{uuid.uuid4().hex[:12]}").strip()
    payload = {
        "user_id": user_id,
        "agent_id": agent_id,
        "session_id": session_id,
        "message": message,
        "system_prompt_variables": {},
        "filter_variables": {},
        "features": [],
    }
    response = request_json(f"{base_url}/v3/inference/chat/", api_key, payload)
    response_text = str(response.get("response", ""))
    if not response_text.strip():
        raise RuntimeError("Lyzr agent chat returned an empty response.")
    return {
        "lyzr_agent_check": "ok",
        "agent_id": agent_id,
        "session_id": session_id,
        "response_chars": len(response_text),
        "response_preview": response_text[:300],
        "inspect": "Open this session/run in Lyzr Studio monitoring or agent chat history to inspect the Studio-side trace.",
    }


def request_json(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(f"Lyzr agent API returned status={exc.code} response={detail!r}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Lyzr agent API request failed: {exc}") from exc
    try:
        data = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Lyzr agent API returned non-JSON response: {response_body[:300]!r}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Lyzr agent API returned an unexpected non-object response.")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
