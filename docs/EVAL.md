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
live Qdrant collection check -> direct Qdrant adapter wrote/read decisions, action_items, and meeting_chunks for team live-88be84c8
live HTTP ingest collection check -> POST /v1/transcripts wrote 1 decision, 1 action item, and 1 meeting chunk to Qdrant for team http-1228ef65
live async ingest check -> POST /v1/transcripts/async returned job-1c45db79a43c, polling showed processing -> completed, and the result included decisions, action_items, meeting_chunks, and trace trace-bdfa48d452a6 for team async-45269136
UI result rendering check -> served frontend includes Summary, Action Items, and Decisions sections; live async job job-eec1c53a8f8e for team ui-00c450c3 returned summary text, action item `document the UI action item`, and decision `use Qdrant for result rendering memory`; frontend sanitizes transcript-derived text before inserting HTML
UI metadata controls check -> upload form now sends visible attendee and agenda inputs instead of fixed JavaScript values, and conflict resolution uses visible resolver name, role, and note inputs; live async job job-7ca16be5dcce for team meta-7daeeea5 preserved attendees `Nina Patel`, `Omar Khan`, agenda `metadata capture`, `review flow`, redacted transcript names, and extracted action `validate resolver inputs`
UI conflict audit check -> frontend exposes `Refresh Conflicts`, calls `/v1/decisions/conflicts`, renders unresolved conflicts with escalation metadata, and removes resolved items from the open conflict audit list after `/v1/decisions/{id}/resolve`; live conflict audit flow for team audit-9b5faa49 created conflicted decision decision-111d8e6d0b, listed it, resolved it as `resolved`, and confirmed the open conflict list became empty
async job retention check -> completed/failed transcript jobs include `expires_at` and expired terminal jobs are purged while in-progress jobs remain pollable
```
