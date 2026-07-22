# Memory

The memory layer is implemented by `backend/app/memory/vector_store.py`.

Runtime selection:
- `MEMORY_BACKEND=local`: JSON-backed local ledger for deterministic tests and demos.
- `MEMORY_BACKEND=qdrant`: Qdrant-backed collections using `qdrant-client`.

## Collections

### `decisions`

Payload:
- `id`
- `meeting_id`
- `team_id`
- `text`
- `source_excerpt`
- `status`: `active`, `superseded`, `conflicted`, or `resolved`
- `related_decision_ids`
- `drift`
- `created_at`
- `resolved_by`
- `resolution_note`

Vector: lazy `sentence-transformers/all-MiniLM-L6-v2` embedding, 384 dimensions, cosine distance. `QdrantVectorMemory` recreates older local/Qdrant collections when their configured vector size does not match `VECTOR_SIZE=384` and `QDRANT_RECREATE_ON_VECTOR_SIZE_MISMATCH` is enabled.

### `action_items`

Payload:
- `id`
- `meeting_id`
- `team_id`
- `task`
- `owner`
- `deadline`
- `source_excerpt`

Vector: embedded from `task`. The manager persists every extracted action item to this collection immediately after extraction, before decision drift writes.

### `meeting_chunks`

Payload:
- `id`
- `meeting_id`
- `team_id`
- `speaker`
- `start_time`
- `end_time`
- `text`
- `redacted_text`
- `source_index`

Vector: embedded from `redacted_text` when present, otherwise `text`. The MVP stores one redacted transcript chunk per processed meeting so recall/drift extensions can ground future retrieval in the original meeting context without retaining PII in the vector text.

## Retention

Meeting chunks should be archived after 12 months. Decisions remain active until superseded, conflicted, or resolved. Redaction maps are temporary sensitive data and must be encrypted at rest in production.

## Live Qdrant Smoke Test

With Qdrant running:

```bash
set MEMORY_BACKEND=qdrant
set SMOKE_QDRANT=1
python scripts/smoke_integrations.py
```

Expected evidence: `qdrant=ok`. The smoke now writes and reads `decisions`, `action_items`, and `meeting_chunks` so all three collection contracts are exercised.
