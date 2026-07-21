# Evaluation

The drift evaluation set is implemented in `scripts/run_eval.py`. It contains 10 hand-written pairs across `New`, `Related`, and `Potential Conflict` labels.

Latest local run:

```text
Decision Drift Eval
cases=10 correct=10 accuracy=100.00%
01 expected=Potential Conflict actual=Potential Conflict ok=True
02 expected=Related actual=Related ok=True
03 expected=New actual=New ok=True
04 expected=Potential Conflict actual=Potential Conflict ok=True
05 expected=Related actual=Related ok=True
06 expected=New actual=New ok=True
07 expected=Potential Conflict actual=Potential Conflict ok=True
08 expected=Related actual=Related ok=True
09 expected=Potential Conflict actual=Potential Conflict ok=True
10 expected=New actual=New ok=True
```

Decision grounding is checked in `backend/tests/test_pipeline.py`: every extracted decision used in the test includes a verbatim `source_excerpt`.

Known evaluation limitation: the current extractor is deterministic and conservative. It is suitable for offline proof of workflow semantics, but production LLM extraction should be evaluated on a larger human-labeled transcript set.

## Integration Smoke

`scripts/smoke_integrations.py` verifies local memory, ADK runtime detection, local trace emission, and optionally live Qdrant. Live Qdrant is opt-in with `SMOKE_QDRANT=1` so CI can still run without Docker.

Latest live stack verification:

```text
docker compose build -> backend image built successfully
docker compose up -d --build backend -> backend and Qdrant running
container ADK detection -> ADKRuntimeStatus(available=True, detail='google.adk import succeeded', version='1.0.0')
container ADK graph smoke -> manager trace emitted adk_graph_finish for meeting_intelligence_adk_manager / parallel_extraction_swarm
container OTLP smoke -> python -m backend.app.observability.otlp_smoke emitted trace-2b1c96c01390 and local receiver captured POST /v1/traces content_type=application/x-protobuf content_length=387
live HTTP ingest trace -> orchestration='adk parallel extraction, sequential drift write'
POST /v1/transcripts first meeting -> active decision persisted through Qdrant
POST /v1/transcripts reversal -> Potential Conflict with prior_decision_id
POST /v1/decisions/{id}/resolve -> status resolved
GET /v1/memory/search -> cited active and resolved decisions
POST /v1/briefs/pre-meeting -> agenda topic 'Qdrant ledger' returned 1 cited prior decision with source excerpt
UI verification -> process, conflict display, resolve, and search all rendered correctly
UI brief verification -> clicking Brief rendered 'Qdrant ledger' with 1 cited active decision
hardening tests -> malformed transcript returns structured 400, dependency outage maps to structured 503, provider rate limit maps to structured 429, Qdrant retry succeeds after transient failures
live hardening check -> stopped Qdrant, GET /v1/memory/search returned 503 dependency_unavailable; restarted Qdrant/backend and ingest plus recall returned 200 with cited source excerpt
conflict resolution guard -> unauthorized resolver role returns authorization_failed; GET /v1/decisions/conflicts marks conflicts older than CONFLICT_ESCALATION_HOURS and emits escalation traces
live Phase 5 check -> conflict listed via GET /v1/decisions/conflicts, observer resolve returned 403 authorization_failed, team_lead resolve returned 200 resolved, unresolved conflict list returned 0
```
