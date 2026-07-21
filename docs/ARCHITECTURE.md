# Architecture

The system is organized as a transcript-to-memory pipeline.

1. `backend/app/services/redaction.py` removes PII before agent processing.
2. `backend/app/agents/manager.py` coordinates three independent extraction agents through a real Google ADK `SequentialAgent`/`ParallelAgent` graph when ADK is installed, persists extracted action items and a redacted meeting chunk, then sequences drift classification and decision persistence.
3. `backend/app/memory/vector_store.py` implements both the local JSON memory contract and `QdrantVectorMemory`, selected by `MEMORY_BACKEND`, for the `decisions`, `action_items`, and `meeting_chunks` collections.
4. `backend/app/agents/decision_drift_agent.py` searches active prior decisions and assigns `New`, `Related`, or `Potential Conflict`.
5. `backend/app/agents/recall_agent.py` turns a natural-language query into cited decision hits and builds pre-meeting briefs from agenda topics.
6. `backend/app/observability/tracing.py` emits an inspectable trace for each agent step; Lyzr Studio inspection can use the Qdrant-backed Knowledge Base/Data Connector path, with optional OTLP export when a collector endpoint is available.
7. `backend/app/services/errors.py` defines stable API error payloads for malformed input, dependency outages, and provider rate limits.
8. `backend/app/api/protocols.py` exposes the existing product capabilities to agent ecosystems: MCP clients can call `tools/list` and `tools/call` at `/mcp` or `/v1/mcp`, and A2A clients can discover the service at `/.well-known/agent-card.json` and call the JSON-RPC endpoint at `/v1/a2a`.
9. `frontend/src/api/client.js` is the browser API client layer used by the static UI in `frontend/src/main.js`; `frontend/src/components/` and `frontend/src/pages/` are present for the required frontend structure as the UI grows beyond the MVP page.

Transcript ingestion has two API modes. `POST /v1/transcripts` remains a synchronous compatibility path for scripts and tests. `POST /v1/transcripts/async` creates an in-process job and `GET /v1/transcripts/jobs/{job_id}` returns `queued`, `processing`, `completed`, or `failed` state for the UI polling flow. Terminal jobs include `expires_at` and are purged after `TRANSCRIPT_JOB_TTL_SECONDS` so the in-process queue does not grow without bound. This keeps the MVP dependency-light while making processing status real; production can replace the in-process executor with Celery/Redis behind the same job contract.

The external documentation used for alignment is current as of 2026-07-21: Google ADK exposes build/run guidance for Python agents and multi-agent workflows, Google Cloud's MCP overview describes MCP hosts/clients/servers and remote HTTP servers, the A2A specification defines a well-known `/.well-known/agent-card.json` discovery document plus JSON-RPC methods such as `message/send` and `tasks/get`, Qdrant quickstart covers local Docker usage, and Lyzr documents enterprise agent observability/integration concepts.

The local mode is intentionally deterministic so the phase gates can be tested without API keys. Production deployment should set `MEMORY_BACKEND=qdrant` and connect Lyzr Studio to the same Qdrant cluster with a Knowledge Base/Data Connector. If Lyzr provides an external OTLP collector URL, traces can also be exported via `LYZR_OTLP_ENDPOINT`; OTLP authentication can be supplied with either `LYZR_API_KEY` for a bearer token or `LYZR_OTLP_HEADERS` for JSON/key-value headers required by the target collector.

`scripts/lyzr_rag_check.py` verifies the Lyzr Studio Knowledge Base/RAG config that points at Qdrant. `scripts/lyzr_live_trace_check.py` is the optional OTLP verification hook: it refuses to run without a real OTLP endpoint and auth, submits a full meeting pipeline trace, then prints the trace id and `meetingmate-agent-swarm` service name for Lyzr Studio inspection.

## Integration Modes

| Mode | Environment | Evidence |
|---|---|---|
| Offline deterministic | `MEMORY_BACKEND=local` | Unit tests and `scripts/run_eval.py` run without cloud credentials. |
| Qdrant live memory | `MEMORY_BACKEND=qdrant`, `QDRANT_URL=http://localhost:6333` | `scripts/smoke_integrations.py` with `SMOKE_QDRANT=1` and the live HTTP ingest check write/read real `decisions`, `action_items`, and `meeting_chunks` collections. |
| ADK extraction graph | `google-adk` installed | Manager trace records ADK availability plus `adk_graph_finish` with `meeting_intelligence_adk_manager`, `parallel_extraction_swarm`, and event count. |
| MCP tool surface | no extra environment | `POST /mcp` or `/v1/mcp` supports `initialize`, `tools/list`, and `tools/call` for transcript ingestion, memory search, pre-meeting briefs, and conflict listing. |
| A2A discovery and task surface | no extra environment | `GET /.well-known/agent-card.json` returns the MeetingMate Agent Card; `POST /v1/a2a` supports `message/send`, `tasks/get`, and `tasks/cancel` over JSON-RPC for the same core skills. |
| Lyzr Studio RAG | `LYZR_API_KEY`, `LYZR_RAG_ID`, optional `LYZR_RAG_COLLECTION` | `scripts/lyzr_rag_check.py` verifies that the Lyzr Knowledge Base uses Qdrant and the expected decisions collection. |
| Optional Lyzr/OTLP tracing | `LYZR_OTLP_ENDPOINT` set, optional `LYZR_API_KEY` / `LYZR_OTLP_HEADERS` | `trace_event` writes local JSONL evidence and emits OpenTelemetry spans to the configured endpoint; `python -m backend.app.observability.otlp_smoke` verifies a real protobuf POST to `/v1/traces`, and `python -m backend.app.observability.pipeline_otlp_smoke` verifies full pipeline agent events in the container. |

## Failure Handling

Malformed transcript and agenda payloads return structured `400` responses. Runtime dependency failures such as Qdrant connection loss are retried with exponential backoff in the Qdrant adapter and surfaced as structured `503` responses. Provider quota/rate-limit errors are classified as structured `429` responses so the UI can show a retryable state instead of a raw server error.

Conflict resolution has a simple MVP authorization boundary: `/v1/decisions/{id}/resolve` accepts only roles listed in `CONFLICT_RESOLVER_ROLES` and defaults to `team_lead`, `decision_owner`, and `admin`. `/v1/decisions/conflicts` lists unresolved conflicts for a team, annotates whether each has exceeded `CONFLICT_ESCALATION_HOURS`, and logs an escalation trace for expired conflicts.
