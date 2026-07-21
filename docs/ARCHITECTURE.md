# Architecture

The system is organized as a transcript-to-memory pipeline.

1. `backend/app/services/redaction.py` removes PII before agent processing.
2. `backend/app/agents/manager.py` coordinates three independent extraction agents in parallel, then sequences drift classification and persistence.
3. `backend/app/memory/vector_store.py` implements the Qdrant-compatible memory contract with local JSON persistence for offline demos.
4. `backend/app/agents/decision_drift_agent.py` searches active prior decisions and assigns `New`, `Related`, or `Potential Conflict`.
5. `backend/app/agents/recall_agent.py` turns a natural-language query into cited decision hits.
6. `backend/app/observability/tracing.py` emits an inspectable trace for each agent step and carries the Lyzr OTLP endpoint configuration.

The external documentation used for alignment is current as of 2026-07-21: Google ADK exposes build/run guidance for Python agents and multi-agent workflows, Google Cloud's MCP overview describes MCP hosts/clients/servers and remote HTTP servers, Qdrant quickstart covers local Docker usage, and Lyzr documents enterprise agent observability/integration concepts.

The local mode is intentionally deterministic so the phase gates can be tested without API keys. Production deployment should set `MEMORY_BACKEND=qdrant`, wire the Qdrant client wrapper, and export traces to Lyzr via OTLP.
