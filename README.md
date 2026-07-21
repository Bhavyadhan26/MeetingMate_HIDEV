# AI Chief of Staff & Meeting Command Center

This project addresses Decision Decay: the tendency for meeting commitments to be forgotten, contradicted, or reinterpreted after the fact. It ingests meeting transcripts, redacts PII, runs a multi-agent extraction pipeline, stores grounded decisions as organizational memory, detects decision drift against prior active decisions, and exposes recall/search plus a demo UI.

## Architecture

```
Transcript Upload
  -> PII Redaction
  -> Google ADK Manager
      -> Summarizer Agent
      -> Action Item Extractor
      -> Conservative Decision Extractor
  -> Decision Drift Agent
      -> Qdrant-compatible vector memory
      -> status: active / conflicted / resolved
  -> Recall Agent + UI
  -> Lyzr/OTLP trace output
```

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Agent orchestration | Google ADK | Docker/runtime path uses an ADK `SequentialAgent` wrapping a `ParallelAgent` for extraction. Local tests use a deterministic fallback when ADK is absent. |
| Vector memory | Qdrant | Persistent semantic memory target for decisions, action items, and meeting chunks. Local mode uses the same payload contract in JSON for offline verification. |
| Observability | Lyzr / OTLP | Agent trace target. Local runs emit inspectable JSONL traces and include the configured Lyzr OTLP endpoint. |
| Backend | FastAPI, Python | API and business services. |
| Frontend | Static HTML/CSS/JS or Vite | Demo command center UI. |
| Eval | Python unittest and scripts | Golden drift scenarios and pipeline checks. |

## Setup

Prerequisites:
- Docker Desktop for Qdrant and the composed demo stack.
- Python 3.12 for local tests/scripts.
- Optional production credentials in `.env`: Gemini, Qdrant API key, and Lyzr OTLP values.

Copy `.env.example` to `.env` and fill only local or real secret values on your machine. Do not commit `.env`.

Run the stack:

```bash
docker compose up --build
```

Backend: `http://localhost:8000`  
Frontend: `http://localhost:5173`  
Qdrant: `http://localhost:6333`

The compose stack runs the backend with `MEMORY_BACKEND=qdrant` and `google-adk` installed, so Qdrant and ADK orchestration are load-bearing in the demo path.

API failures use stable JSON error details: malformed payloads return `malformed_transcript`, dependency outages return `dependency_unavailable`, and provider rate limits return `provider_rate_limited`. Qdrant read/write operations retry briefly before surfacing a dependency failure. The UI uses `POST /v1/transcripts/async` plus `GET /v1/transcripts/jobs/{job_id}` polling so users see queued/processing/completed state instead of waiting on a blank request. Completed and failed transcript jobs expire after `TRANSCRIPT_JOB_TTL_SECONDS`.

Run integration smoke checks:

```bash
python scripts/smoke_integrations.py
```

To verify the container OTLP export path against a local receiver:

```bash
docker compose exec backend python -m backend.app.observability.otlp_smoke
```

Use `LYZR_OTLP_ENDPOINT` for the collector URL. Set `LYZR_API_KEY` for bearer auth, or `LYZR_OTLP_HEADERS` for JSON or comma-separated header values when the target collector requires custom headers.

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

## Known Limitations

The repository currently ships an offline-verifiable MVP plus live Qdrant, ADK, and OTLP tracing adapters. Local tests run without cloud credentials by using deterministic adapters; the Docker demo uses Qdrant as the active memory backend and ADK for extraction orchestration. Real audio ingestion, Auth0 RBAC, Slack/email escalation, and full Celery/Redis queueing are scoped as stretch work after the core transcript path is verified.

## Project Structure

The repo follows the required structure from the build prompt: backend agents, services, models, memory, observability, tests, frontend UI, docs, and scripts.
