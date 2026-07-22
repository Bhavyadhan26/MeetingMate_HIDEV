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

Vector: lazy `sentence-transformers/all-MiniLM-L6-v2` embedding, 384 dimensions, cosine distance. `QdrantVectorMemory` recreates older local/Qdrant collections when their configured vector size does not match `VECTOR_SIZE=384` and `QDRANT_RECREATE_ON_VECTOR_SIZE_MISMATCH` is enabled. Collection creation, deletion, and payload-index setup tolerate common concurrent startup races such as "already exists" and "not found" during migration.

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

Decision status lifecycle:
- `active`: the current accepted decision.
- `conflicted`: an unacknowledged reversal of an active prior decision.
- `resolved`: a human reviewer resolved a conflict through `/v1/decisions/{id}/resolve`.
- `superseded`: a newer decision explicitly acknowledged that it replaces, supersedes, resolves, or overrides the prior active decision.

## Relational Metadata

`backend/app/persistence/database.py` stores non-vector records in PostgreSQL when `DATABASE_URL` is configured, and in SQLite when running lightweight local tests.

Tables:
- `meetings`: meeting id, team id, title, attendees JSON, agenda JSON, created timestamp.
- `redaction_maps`: meeting id, team id, AES-GCM-256 encrypted redaction map JSON. Set `REDACTION_MAP_ENCRYPTION_KEY` outside local development.
- `transcript_jobs`: durable queue and job history for text/audio transcript processing.
- `users`, `teams`, `team_memberships`: schema placeholders for auth/RBAC and team structure.

Qdrant remains responsible only for semantic memory: embedded decisions, action items, and meeting chunks.

## Clear Collections

`POST /v1/admin/qdrant/clear` deletes and recreates the active Qdrant collections: `decisions`, `action_items`, and `meeting_chunks`. The frontend exposes this as `Clear Qdrant`. It does not delete PostgreSQL metadata or job history.

## Live Qdrant Smoke Test

With Qdrant running:

```bash
set MEMORY_BACKEND=qdrant
set SMOKE_QDRANT=1
python scripts/smoke_integrations.py
```

Expected evidence: `qdrant=ok`. The smoke now writes and reads `decisions`, `action_items`, and `meeting_chunks` so all three collection contracts are exercised.
