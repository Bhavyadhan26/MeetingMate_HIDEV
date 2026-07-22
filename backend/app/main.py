from __future__ import annotations

import os
from contextlib import asynccontextmanager

try:
    from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
except Exception:  # pragma: no cover
    FastAPI = None

from backend.app.api.protocols import a2a_agent_card, handle_a2a_jsonrpc, handle_mcp_jsonrpc
from backend.app.api.routes import clear_qdrant_collections, enqueue_audio_transcript, enqueue_transcript, get_decision, get_transcript_job, list_unresolved_conflicts, pre_meeting_brief, process_transcript, resolve_decision_with_role, search_memory, stop_worker
from backend.app.persistence import get_metadata_store
from backend.app.security import UserContext, auth_required, require_role, require_team_access, require_user
from backend.app.services.errors import AppError


if FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        stop_worker()

    app = FastAPI(title="AI Chief of Staff Meeting Command Center", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    if os.getenv("REQUIRE_HTTPS", "0").lower() in {"1", "true", "yes"}:
        app.add_middleware(HTTPSRedirectMiddleware)

    @app.post("/v1/transcripts")
    def ingest_transcript(payload: dict, user: UserContext = Depends(require_user)) -> dict:
        _authorize_payload_team(user, payload)
        return _handle_app_error(lambda: process_transcript(payload))

    @app.post("/v1/transcripts/async")
    def ingest_transcript_async(payload: dict, user: UserContext = Depends(require_user)) -> dict:
        _authorize_payload_team(user, payload)
        return _handle_app_error(lambda: enqueue_transcript(payload))

    @app.post("/v1/transcripts/upload")
    async def upload_audio_transcript(
        file: UploadFile = File(...),
        title: str = Form("Untitled audio meeting"),
        team_id: str = Form("demo-team"),
        attendees: str = Form(""),
        agenda: str = Form(""),
        user: UserContext = Depends(require_user),
    ) -> dict:
        _authorize_team(user, team_id)
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
    def transcript_job(job_id: str, user: UserContext = Depends(require_user)) -> dict:
        result = get_transcript_job(job_id)
        if "error" in result and result["error"] == "Job not found":
            raise HTTPException(status_code=404, detail=result["error"])
        team_id = _job_team_id(result)
        if team_id:
            _authorize_team(user, team_id)
        return result

    @app.post("/v1/admin/qdrant/clear")
    def clear_qdrant(user: UserContext = Depends(require_user)) -> dict:
        require_role(user, {"admin", "platform_admin"})
        return _handle_app_error(clear_qdrant_collections)

    @app.get("/v1/auth/config")
    def auth_config() -> dict:
        return {
            "required": auth_required(),
            "domain": os.getenv("AUTH0_DOMAIN", ""),
            "client_id": os.getenv("AUTH0_CLIENT_ID", os.getenv("MEETINGMATE_AUTH0_CLIENT_ID", "")),
            "audience": os.getenv("AUTH0_AUDIENCE", ""),
        }

    @app.get("/v1/memory/search")
    def memory_search(query: str, team_id: str = "demo-team", user: UserContext = Depends(require_user)) -> dict:
        _authorize_team(user, team_id)
        return _handle_app_error(lambda: search_memory(query, team_id))

    @app.post("/v1/briefs/pre-meeting")
    def brief_pre_meeting(payload: dict, user: UserContext = Depends(require_user)) -> dict:
        _authorize_payload_team(user, payload)
        return _handle_app_error(lambda: pre_meeting_brief(payload))

    @app.post("/v1/decisions/{decision_id}/resolve")
    def decision_resolve(decision_id: str, payload: dict, user: UserContext = Depends(require_user)) -> dict:
        def run() -> dict:
            existing = get_decision(decision_id)
            if not existing:
                raise HTTPException(status_code=404, detail="Decision not found")
            _authorize_team(user, str(existing.get("team_id", "")))
            require_role(user, {"team_lead", "decision_owner", "admin", "platform_admin"})
            result = resolve_decision_with_role(
                decision_id,
                payload.get("resolver") or user.email or user.subject,
                payload.get("note", "Resolved by human review."),
                next(iter(user.roles), "team_lead"),
            )
            if "error" in result:
                raise HTTPException(status_code=404, detail=result["error"])
            return result

        return _handle_app_error(run)

    @app.get("/v1/decisions/conflicts")
    def decision_conflicts(team_id: str = "demo-team", user: UserContext = Depends(require_user)) -> dict:
        _authorize_team(user, team_id)
        return _handle_app_error(lambda: list_unresolved_conflicts(team_id))

    @app.get("/.well-known/agent-card.json")
    def agent_card() -> dict:
        return a2a_agent_card()

    @app.post("/v1/a2a")
    def a2a_jsonrpc(payload: dict, user: UserContext = Depends(require_user)) -> dict:
        _sync_user(user)
        return _handle_app_error(lambda: handle_a2a_jsonrpc(payload))

    @app.post("/mcp")
    def mcp_jsonrpc(payload: dict, user: UserContext = Depends(require_user)) -> dict:
        _sync_user(user)
        return _handle_app_error(lambda: handle_mcp_jsonrpc(payload))

    @app.post("/v1/mcp")
    def mcp_jsonrpc_v1(payload: dict, user: UserContext = Depends(require_user)) -> dict:
        _sync_user(user)
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


    def _authorize_payload_team(user: UserContext, payload: dict) -> None:
        _authorize_team(user, str(payload.get("team_id", "demo-team")))


    def _authorize_team(user: UserContext, team_id: str) -> None:
        _sync_user(user)
        require_team_access(user, team_id)


    def _sync_user(user: UserContext) -> None:
        try:
            get_metadata_store().sync_user_context(user.subject, user.email, user.roles, user.teams)
        except Exception:
            if user.subject != "local-dev":
                raise


    def _job_team_id(job: dict) -> str:
        result = job.get("result") or {}
        if result.get("meeting"):
            return str(result["meeting"].get("team_id", ""))
        return str(job.get("team_id") or "")
else:
    app = None
