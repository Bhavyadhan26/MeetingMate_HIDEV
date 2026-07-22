from __future__ import annotations

try:
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
except Exception:  # pragma: no cover
    FastAPI = None

from backend.app.api.protocols import a2a_agent_card, handle_a2a_jsonrpc, handle_mcp_jsonrpc
from backend.app.api.routes import enqueue_audio_transcript, enqueue_transcript, get_transcript_job, list_unresolved_conflicts, pre_meeting_brief, process_transcript, resolve_decision_with_role, search_memory
from backend.app.services.errors import AppError


if FastAPI:
    app = FastAPI(title="AI Chief of Staff Meeting Command Center")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.post("/v1/transcripts")
    def ingest_transcript(payload: dict) -> dict:
        return _handle_app_error(lambda: process_transcript(payload))

    @app.post("/v1/transcripts/async")
    def ingest_transcript_async(payload: dict) -> dict:
        return _handle_app_error(lambda: enqueue_transcript(payload))

    @app.post("/v1/transcripts/upload")
    async def upload_audio_transcript(
        file: UploadFile = File(...),
        title: str = Form("Untitled audio meeting"),
        team_id: str = Form("demo-team"),
        attendees: str = Form(""),
        agenda: str = Form(""),
    ) -> dict:
        content = await file.read()
        return _handle_app_error(
            lambda: enqueue_audio_transcript(
                filename=file.filename or "upload",
                content=content,
                content_type=file.content_type,
                title=title,
                team_id=team_id,
                attendees=_parse_form_list(attendees),
                agenda=_parse_form_list(agenda),
            )
        )

    @app.get("/v1/transcripts/jobs/{job_id}")
    def transcript_job(job_id: str) -> dict:
        result = get_transcript_job(job_id)
        if "error" in result and result["error"] == "Job not found":
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    @app.get("/v1/memory/search")
    def memory_search(query: str, team_id: str = "demo-team") -> dict:
        return _handle_app_error(lambda: search_memory(query, team_id))

    @app.post("/v1/briefs/pre-meeting")
    def brief_pre_meeting(payload: dict) -> dict:
        return _handle_app_error(lambda: pre_meeting_brief(payload))

    @app.post("/v1/decisions/{decision_id}/resolve")
    def decision_resolve(decision_id: str, payload: dict) -> dict:
        def run() -> dict:
            result = resolve_decision_with_role(
                decision_id,
                payload.get("resolver", "Team Lead"),
                payload.get("note", "Resolved by human review."),
                payload.get("resolver_role", "team_lead"),
            )
            if "error" in result:
                raise HTTPException(status_code=404, detail=result["error"])
            return result

        return _handle_app_error(run)

    @app.get("/v1/decisions/conflicts")
    def decision_conflicts(team_id: str = "demo-team") -> dict:
        return _handle_app_error(lambda: list_unresolved_conflicts(team_id))

    @app.get("/.well-known/agent-card.json")
    def agent_card() -> dict:
        return a2a_agent_card()

    @app.post("/v1/a2a")
    def a2a_jsonrpc(payload: dict) -> dict:
        return _handle_app_error(lambda: handle_a2a_jsonrpc(payload))

    @app.post("/mcp")
    def mcp_jsonrpc(payload: dict) -> dict:
        return _handle_app_error(lambda: handle_mcp_jsonrpc(payload))

    @app.post("/v1/mcp")
    def mcp_jsonrpc_v1(payload: dict) -> dict:
        return _handle_app_error(lambda: handle_mcp_jsonrpc(payload))


    def _handle_app_error(operation: object) -> dict:
        try:
            return operation()
        except HTTPException:
            raise
        except AppError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


    def _parse_form_list(value: str) -> list[str]:
        return [item.strip() for item in str(value or "").replace("\n", ",").split(",") if item.strip()]
else:
    app = None
