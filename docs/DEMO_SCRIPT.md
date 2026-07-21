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

5. Click resolve on the conflict.

Expected result: the decision status changes to `resolved`.

6. Search memory for:

```text
What did we decide about Qdrant?
```

Expected result: the recall answer cites the relevant source excerpts.

7. Inspect `backend/app/observability/local_traces.jsonl`.

Expected result: trace records exist for manager, summarizer, action item extractor, decision extractor, decision drift, and recall.
