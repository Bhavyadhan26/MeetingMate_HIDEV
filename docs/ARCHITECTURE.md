# Architecture

The system is organized as a transcript-to-memory pipeline.

1. `backend/app/services/redaction.py` removes PII before agent processing.
2. `backend/app/agents/manager.py` coordinates three independent extraction agents through a real Google ADK `SequentialAgent`/`ParallelAgent` graph when ADK is installed, then sequences drift classification and persistence.
3. `backend/app/memory/vector_store.py` implements both the local JSON memory contract and `QdrantVectorMemory`, selected by `MEMORY_BACKEND`.
4. `backend/app/agents/decision_drift_agent.py` searches active prior decisions and assigns `New`, `Related`, or `Potential Conflict`.
5. `backend/app/agents/recall_agent.py` turns a natural-language query into cited decision hits.
6. `backend/app/observability/tracing.py` emits an inspectable trace for each agent step and carries the Lyzr OTLP endpoint configuration.

The external documentation used for alignment is current as of 2026-07-21: Google ADK exposes build/run guidance for Python agents and multi-agent workflows, Google Cloud's MCP overview describes MCP hosts/clients/servers and remote HTTP servers, Qdrant quickstart covers local Docker usage, and Lyzr documents enterprise agent observability/integration concepts.

The local mode is intentionally deterministic so the phase gates can be tested without API keys. Production deployment should set `MEMORY_BACKEND=qdrant` and export traces to Lyzr via `LYZR_OTLP_ENDPOINT`. OTLP authentication can be supplied with either `LYZR_API_KEY` for a bearer token or `LYZR_OTLP_HEADERS` for JSON/key-value headers required by the target collector.

## Integration Modes

| Mode | Environment | Evidence |
|---|---|---|
| Offline deterministic | `MEMORY_BACKEND=local` | Unit tests and `scripts/run_eval.py` run without cloud credentials. |
| Qdrant live memory | `MEMORY_BACKEND=qdrant`, `QDRANT_URL=http://localhost:6333` | `scripts/smoke_integrations.py` with `SMOKE_QDRANT=1` upserts and searches a real Qdrant collection. |
| ADK extraction graph | `google-adk` installed | Manager trace records ADK availability plus `adk_graph_finish` with `meeting_intelligence_adk_manager`, `parallel_extraction_swarm`, and event count. |
| Lyzr/OTLP tracing | `LYZR_OTLP_ENDPOINT` set, optional `LYZR_API_KEY` / `LYZR_OTLP_HEADERS` | `trace_event` writes local JSONL evidence and emits OpenTelemetry spans to the configured endpoint; `python -m backend.app.observability.otlp_smoke` verifies a real protobuf POST to `/v1/traces` in the container. |
