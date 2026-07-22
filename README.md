# AI Chief of Staff & Meeting Command Center

This project addresses Decision Decay: the tendency for meeting commitments to be forgotten, contradicted, or reinterpreted after the fact. It ingests meeting transcripts, redacts PII, runs a multi-agent extraction pipeline, stores grounded decisions as organizational memory, detects decision drift against prior active decisions, and exposes recall/search plus a demo UI.

## Architecture

```
Text Transcript or Audio Upload
  -> Deepgram STT for audio (Nova-2, diarization)
  -> PII Redaction
  -> PostgreSQL metadata + durable job history
  -> Google ADK Manager
      -> Groq Summarizer Agent
      -> Groq Action Item Extractor
      -> Groq Conservative Decision Extractor
  -> Decision Drift Agent
      -> all-MiniLM-L6-v2 embeddings
      -> Qdrant-compatible vector memory
      -> status: active / conflicted / resolved
  -> Recall Agent + UI
  -> Lyzr Studio Qdrant Knowledge Base + optional OTLP trace output
```

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Agent orchestration | Google ADK | Docker/runtime path uses an ADK `SequentialAgent` wrapping a `ParallelAgent` for extraction. Local tests use a deterministic fallback when ADK is absent. |
| LLM inference | Groq `llama-3.1-8b-instant` | Summarizer, action item extractor, decision extractor, drift classifier, and recall agent use Groq JSON output when `GROQ_API_KEY` is configured. |
| Speech-to-text | Deepgram Nova-2 | Audio upload path uses diarization, punctuation, utterances, and speaker-tagged transcript formatting. |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Lazy-loaded 384-dimensional semantic vectors for drift, recall, and pre-meeting briefs. |
| Vector memory | Qdrant | Persistent semantic memory target for decisions, action items, and meeting chunks. Local mode uses the same payload contract in JSON for offline verification. |
| Relational persistence | PostgreSQL, SQLite fallback | Meeting metadata, redaction maps, team/user tables, and transcript job history. Docker uses Postgres; local tests can use SQLite files. |
| Auth/RBAC | Auth0 JWT, team claims | FastAPI verifies RS256 bearer tokens when Auth0 is configured, enforces team membership, and syncs verified users/teams into Postgres. |
| Observability | Lyzr Studio / OTLP | Lyzr Studio reads the Qdrant-backed decision memory through a Knowledge Base/Data Connector; local runs emit inspectable JSONL traces, and OTLP export is available when Lyzr provides a collector endpoint. |
| Backend | FastAPI, Python | API and business services. |
| Frontend | Static HTML/CSS/JS or Vite | Demo command center UI. |
| Eval | Python unittest and scripts | Golden drift scenarios and pipeline checks. |

## Setup

Prerequisites:
- Docker Desktop for Qdrant and the composed demo stack.
- Python 3.12 for local tests/scripts.
- Optional production credentials in `.env`: Groq, Deepgram, Qdrant API key, and Lyzr OTLP values.

Copy `.env.example` to `.env` and fill only local or real secret values on your machine. Do not commit `.env`.

For Qdrant Cloud and Lyzr Studio connector setup, see [docs/LYZR_QDRANT_SETUP.md](docs/LYZR_QDRANT_SETUP.md). `docker-compose.yml` reads `MEMORY_BACKEND`, `QDRANT_URL`, `QDRANT_API_KEY`, and optional Lyzr values from `.env`; when these are absent it falls back to the local Qdrant container.

Run the stack:

```bash
docker compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- Qdrant: `http://localhost:6333`
- PostgreSQL: `localhost:5432`

The compose stack runs the backend with `MEMORY_BACKEND=qdrant` and `google-adk` installed, so Qdrant and ADK orchestration are load-bearing in the demo path.

API failures use stable JSON error details: malformed payloads return `malformed_transcript`, dependency outages return `dependency_unavailable`, and provider rate limits return `provider_rate_limited`. Qdrant read/write operations retry briefly before surfacing a dependency failure. The UI uses `POST /v1/transcripts/async` plus `GET /v1/transcripts/jobs/{job_id}` polling so users see queued/processing/completed state instead of waiting on a blank request. Jobs are persisted in PostgreSQL in Docker, with a SQLite fallback for local tests, so completed job history survives backend restarts. Completed and failed transcript jobs expire after `TRANSCRIPT_JOB_TTL_SECONDS`.

The Recall panel includes a `Clear Qdrant` button wired to `POST /v1/admin/qdrant/clear`. It deletes and recreates the configured `decisions`, `action_items`, and `meeting_chunks` collections using the active Qdrant URL/API key from the backend environment. PostgreSQL metadata and job history are intentionally not deleted by this control.

Auth0 is enabled automatically when `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` are set, unless `AUTH_REQUIRED=0` is explicitly configured for local development. Bearer tokens must include team claims under `https://meetingmate/teams` and role claims under `https://meetingmate/roles` by default; override the namespace with `AUTH0_CLAIMS_NAMESPACE`. The frontend reads `/v1/auth/config`, starts Auth0 Universal Login, and attaches access tokens to API calls.

Agent clients can use the same backend through protocol adapters. MCP clients can call `POST /mcp` or `POST /v1/mcp` with `tools/list` and `tools/call`. A2A clients can discover the agent at `GET /.well-known/agent-card.json` and send JSON-RPC messages to `POST /v1/a2a`. When auth is enabled, MCP/A2A JSON-RPC endpoints also require bearer tokens.

Audio uploads use `POST /v1/transcripts/upload` with an `mp3`, `wav`, `m4a`, or `ogg` file. The backend saves the file under `backend/audio_uploads/{job_id}/`, transcribes it with Deepgram Nova-2 diarization and punctuation, converts the response into speaker-tagged transcript lines, runs the normal async MeetingPipeline job, and removes the uploaded file directory when processing finishes.

Run integration smoke checks:

```bash
python scripts/smoke_integrations.py
```

To verify the container OTLP export path against a local receiver:

```bash
docker compose exec backend python -m backend.app.observability.otlp_smoke
docker compose exec backend python -m backend.app.observability.pipeline_otlp_smoke
```

Use `LYZR_OTLP_ENDPOINT` for the collector URL. Set `LYZR_API_KEY` for bearer auth, or `LYZR_OTLP_HEADERS` for JSON or comma-separated header values when the target collector requires custom headers.

To verify a Lyzr Studio Knowledge Base/RAG config that points at Qdrant, set `LYZR_API_KEY`, `LYZR_RAG_ID`, and optionally `LYZR_RAG_COLLECTION`, then run:

```bash
python scripts/lyzr_rag_check.py
python scripts/lyzr_sync_qdrant_decisions.py
python scripts/lyzr_rag_retrieve_check.py
```

To verify an actual Lyzr Studio agent run against that Knowledge Base, attach the Knowledge Base to a Studio agent, set `LYZR_AGENT_ID`, and run:

```bash
python scripts/lyzr_create_agent.py
python scripts/lyzr_agent_check.py
```

To submit a full pipeline trace to a real Lyzr OTLP collector, set the Lyzr endpoint and auth values in the backend container environment, then run:

```bash
docker compose exec backend python -m backend.app.observability.lyzr_live_trace_check
```

The OTLP command prints the trace id and expected service name (`meetingmate-agent-swarm`) to inspect in Lyzr Studio. Skip it when the workspace does not expose an external OTLP endpoint; Lyzr Studio agent runs against the Qdrant Knowledge Base are the inspectable Studio path.

To require a live Qdrant check:

```bash
set MEMORY_BACKEND=qdrant
set SMOKE_QDRANT=1
python scripts/smoke_integrations.py
```

## Demo

See [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). The shortest path is:

```bash
python scripts/demo_walkthrough.py
```

This exercises the running Docker stack through the API: process the baseline meeting, process a contradictory meeting, list and resolve the conflict, search recall, generate a pre-meeting brief, and inspect the Qdrant decisions collection. `scripts/seed_demo_data.py` remains available for offline local-ledger seeding when you are not running the compose stack.

The UI also includes a pre-meeting brief panel. Enter agenda topics such as `Qdrant ledger` after seeding or processing meetings; the backend calls `/v1/briefs/pre-meeting` and returns cited prior decisions for each topic.

## Eval

```bash
python scripts/run_eval.py
```

The latest verified output is recorded in [docs/EVAL.md](docs/EVAL.md).

Run the git-history secret guard before release commits:

```bash
python scripts/check_no_secrets_tracked.py
```

Run the full local release audit:

```bash
python scripts/final_audit.py
```

With the Docker stack running, include live Qdrant and demo walkthrough checks:

```bash
set FINAL_AUDIT_LIVE=1
python scripts/final_audit.py
```

To prove the README path from a fresh clone on alternate local ports:

```bash
python scripts/fresh_clone_audit.py
```

## Known Limitations

The repository currently ships an offline-verifiable MVP plus live Qdrant, PostgreSQL metadata persistence, encrypted redaction maps, durable SQLite/Postgres job history, Auth0 JWT/RBAC, ADK, Groq, Deepgram audio ingestion, Lyzr Studio Knowledge Base verification, and optional OTLP tracing adapters. Local tests can still run without cloud credentials by using deterministic fallbacks; the Docker demo uses Qdrant as the active memory backend, Postgres as the metadata backend, MiniLM semantic embeddings, ADK for extraction orchestration, and Groq when `GROQ_API_KEY` is set. TLS 1.3 should be terminated by a production reverse proxy or cloud load balancer; the app includes `REQUIRE_HTTPS=1` redirect support, while local Docker remains HTTP for development. Slack/email escalation and full Celery/Redis queueing remain scoped as stretch work after the core transcript and audio paths.

## Project Structure

The repo follows the required structure from the build prompt: backend agents, services, models, memory, observability, tests, frontend UI, docs, and scripts.
