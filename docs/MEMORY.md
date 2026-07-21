# Memory

The memory layer is Qdrant-compatible and implemented locally by `backend/app/memory/vector_store.py` for offline verification.

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

Vector: deterministic 64-dimensional token-hash embedding in local mode. Production should replace this with the selected embedding model and Qdrant vectors.

### `action_items`

Payload:
- `id`
- `meeting_id`
- `team_id`
- `task`
- `owner`
- `deadline`
- `source_excerpt`

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

## Retention

Meeting chunks should be archived after 12 months. Decisions remain active until superseded, conflicted, or resolved. Redaction maps are temporary sensitive data and must be encrypted at rest in production.
