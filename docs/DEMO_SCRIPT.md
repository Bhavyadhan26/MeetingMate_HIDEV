# Demo Script

1. Start the backend and frontend with `docker compose up --build`.
2. Open `http://localhost:5173`.
3. Process this first transcript:

```text
Asha Rao: We decided use Qdrant as the persistent vector ledger. Marco will prepare the ingestion checklist by Friday.
```

Expected result: one active decision and one action item.

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

6. Click resolve on the conflict.

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

9. Inspect `backend/app/observability/local_traces.jsonl` in local mode, or the configured OTLP/Lyzr sink when `LYZR_OTLP_ENDPOINT` is set.

Expected result: trace records exist for manager, summarizer, action item extractor, decision extractor, decision drift, and recall.

10. Verify the OTLP exporter path from inside the backend container:

```bash
docker compose exec backend python -m backend.app.observability.otlp_smoke
```

Expected result: JSON output includes a request with `path` `/v1/traces`, `content_type` `application/x-protobuf`, and non-zero `content_length`.

11. Confirm Qdrant contains decisions:

```bash
curl http://localhost:6333/collections/decisions
```

Expected result: `points_count` increases after processing meetings.
