from __future__ import annotations

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
except Exception:  # pragma: no cover
    FastAPI = None

from backend.app.api.routes import pre_meeting_brief, process_transcript, resolve_decision, search_memory
from backend.app.services.errors import AppError


if FastAPI:
    app = FastAPI(title="AI Chief of Staff Meeting Command Center")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.post("/v1/transcripts")
    def ingest_transcript(payload: dict) -> dict:
        return _handle_app_error(lambda: process_transcript(payload))

    @app.get("/v1/memory/search")
    def memory_search(query: str, team_id: str = "demo-team") -> dict:
        return _handle_app_error(lambda: search_memory(query, team_id))

    @app.post("/v1/briefs/pre-meeting")
    def brief_pre_meeting(payload: dict) -> dict:
        return _handle_app_error(lambda: pre_meeting_brief(payload))

    @app.post("/v1/decisions/{decision_id}/resolve")
    def decision_resolve(decision_id: str, payload: dict) -> dict:
        def run() -> dict:
            result = resolve_decision(decision_id, payload.get("resolver", "Team Lead"), payload.get("note", "Resolved by human review."))
            if "error" in result:
                raise HTTPException(status_code=404, detail=result["error"])
            return result

        return _handle_app_error(run)


    def _handle_app_error(operation: object) -> dict:
        try:
            return operation()
        except HTTPException:
            raise
        except AppError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
else:
    app = None
