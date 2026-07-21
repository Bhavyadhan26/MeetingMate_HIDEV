# Demo Script

1. Start the backend and frontend with `docker compose up --build`.
2. Open `http://localhost:5173`.

To verify the full API-backed walkthrough without manual clicks, run:

```bash
python scripts/demo_walkthrough.py
```

Expected result: JSON output includes `demo_walkthrough: ok`, one conflicted decision that resolves to `resolved`, recall citations, brief citations, and an inspectable Qdrant `decisions` collection.

For offline local-ledger seeding without the compose stack, use `python scripts/seed_demo_data.py`; that helper writes `backend/app/memory/local_ledger.json` and is separate from the Qdrant-backed Docker demo.

Manual UI walkthrough:

3. Process this first transcript:

```text
Asha Rao: We decided use Qdrant as the persistent vector ledger. Marco will prepare the ingestion checklist by Friday.
```

Expected result: the status badge moves through queued/processing, then the summary, one active decision, and one action item appear.

The upload form sends the visible team id, attendee list, and meeting agenda fields with the transcript. The default demo values are `demo-team`, `Asha Rao, Marco Lee`, and `memory ledger, ingestion`.

4. Process this second transcript:

```text
Decision: no longer use Qdrant as the persistent vector ledger.
```

Expected result: the new decision is marked `conflicted` with `Potential Conflict`.

5. Optionally inspect unresolved conflicts:

```bash
curl "http://localhost:8000/v1/decisions/conflicts?team_id=demo-team"
```

Expected result: the conflict appears with escalation metadata.

You can also click `Refresh Conflicts` in the UI. Expected result: the open conflict count updates and the unresolved conflict appears in the conflict audit list.

6. Click resolve on the conflict. Use one of the allowed resolver roles shown in the form, such as `team_lead`.

Expected result: the decision status changes to `resolved`.

7. Search memory for:

```text
What did we decide about Qdrant?
```

Expected result: the recall answer cites the relevant source excerpts.

8. Generate a pre-meeting brief with this agenda topic:

```text
Qdrant ledger
```

Expected result: the brief topic cites the prior Qdrant decision with its source excerpt.

9. Inspect `backend/app/observability/local_traces.jsonl` in local mode. For Lyzr Studio, attach the Qdrant-backed Knowledge Base to a Lyzr agent and inspect that agent run in Studio monitoring/traces.

Expected result: trace records exist for manager, summarizer, action item extractor, decision extractor, decision drift, and recall.

10. Verify the OTLP exporter path from inside the backend container:

```bash
docker compose exec backend python -m backend.app.observability.otlp_smoke
docker compose exec backend python -m backend.app.observability.pipeline_otlp_smoke
```

Expected result: JSON output includes a request with `path` `/v1/traces`, `content_type` `application/x-protobuf`, and non-zero `content_length`; the pipeline smoke also lists `manager`, `summarizer`, `action_item_extractor`, `decision_extractor`, and `decision_drift_agent`.

11. Verify the Lyzr Studio Knowledge Base/RAG config that points at Qdrant:

```bash
python scripts/lyzr_rag_check.py
python scripts/lyzr_rag_retrieve_check.py
```

Expected result: JSON output includes `lyzr_rag_check: ok`, the Qdrant vector store provider, the configured decisions collection, and `lyzr_rag_retrieve_check: ok` with at least one result.

12. If a Lyzr Studio agent has the Knowledge Base attached, verify an actual Studio-side run:

```bash
python scripts/lyzr_agent_check.py
```

Expected result: JSON output includes `lyzr_agent_check: ok` and a `session_id` that can be opened in Lyzr Studio monitoring or agent chat history.

To submit the same kind of full pipeline trace to a real Lyzr OTLP collector, set `LYZR_OTLP_ENDPOINT` and either `LYZR_API_KEY` or `LYZR_OTLP_HEADERS` in the backend container, then run:

```bash
docker compose exec backend python -m backend.app.observability.lyzr_live_trace_check
```

Expected result: JSON output includes `lyzr_live_trace_check: submitted`, a trace id, and the agent list to verify in Lyzr Studio. Skip this when your Lyzr workspace does not expose an external OTLP endpoint.

13. Confirm Qdrant contains decisions:

```bash
curl http://localhost:6333/collections/decisions
```

Expected result: `points_count` increases after processing meetings.
