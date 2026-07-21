# Lyzr + Qdrant Setup

This project writes meeting memory to Qdrant. Lyzr can read that memory by connecting to the same Qdrant cluster as a Data Connector. That is separate from OTLP tracing: the Qdrant connector enables retrieval, while an OTLP endpoint is only needed if Lyzr provides a collector URL for external OpenTelemetry traces.

## MeetingMate Environment

Create `D:\MeetingMate\.env` from `.env.example` and keep real values local:

```env
MEMORY_BACKEND=qdrant
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your-qdrant-cluster-api-key
LYZR_API_KEY=your-lyzr-api-key
LYZR_RAG_ID=your-lyzr-knowledge-base-id
LYZR_RAG_COLLECTION=decisions
LYZR_RAG_QUERY=What did we decide about Qdrant?
LYZR_AGENT_ID=your-lyzr-agent-id-after-attaching-the-knowledge-base
```

`docker-compose.yml` reads those values automatically. If they are absent, the backend uses the local Qdrant service at `http://qdrant:6333`.

Restart the stack after changing `.env`:

```bash
docker compose up -d --build
```

Then ingest a transcript through the UI or run the demo walkthrough. MeetingMate will create and populate these Qdrant collections:

- `decisions`
- `action_items`
- `meeting_chunks`

## Qdrant Cloud

In Qdrant Cloud:

1. Open the target cluster.
2. Copy the cluster endpoint URL.
3. Create a cluster database API key with read/write access.
4. Confirm the cluster permits access from Lyzr and from your local Docker host.

Use a cluster database API key, not an account management key, unless Qdrant explicitly grants that key database access.

## Lyzr Studio

In Lyzr Studio:

1. Open **Connections** or **Data Connectors**.
2. Choose **Qdrant**.
3. Add a connection named `MeetingMate_Qdrant`.
4. Enter the Qdrant cluster URL and cluster database API key.
5. Test the connection and save it.
6. Create a Knowledge Base or vector-backed resource from that connector.
7. Select the `decisions` collection first.
8. Attach the Knowledge Base to a Lyzr agent.
9. Copy the agent id into `LYZR_AGENT_ID` in `.env`.
10. Run queries such as:
   - `What did we decide about Qdrant?`
   - `List conflicted decisions.`
   - `What active decisions exist for the platform team?`

Runs made through that Lyzr agent should appear in Lyzr Studio monitoring/traces.

The current validated Lyzr configuration should look like this:

- vector store provider: `Qdrant [MeetingMate_Qdrant]`
- source collection intent: `decisions`
- semantic data model: `false`

Verify the saved Lyzr Knowledge Base/RAG config from the repo:

```bash
python scripts/lyzr_rag_check.py
python scripts/lyzr_rag_retrieve_check.py
```

Expected result: `lyzr_rag_check` is `ok`, `vector_store_provider` contains `Qdrant`, and `collection_name` contains the configured `LYZR_RAG_COLLECTION` value. `lyzr_rag_retrieve_check` should also return at least one result for the configured query. Together, these confirm the Lyzr Studio side is connected to populated Qdrant-backed MeetingMate memory.

Verify a real Lyzr Studio agent invocation against that Knowledge Base:

```bash
python scripts/lyzr_agent_check.py
```

Expected result: `lyzr_agent_check` is `ok`, the output includes a generated `session_id`, and the same session can be inspected in Lyzr Studio monitoring or agent chat history. This command requires `LYZR_AGENT_ID`; it intentionally fails if no Studio agent is attached yet.

## OTLP Endpoint

`LYZR_OTLP_ENDPOINT` is not the Lyzr Agent API base URL. It must be an OTLP/HTTP trace collector endpoint that accepts protobuf POSTs. If Lyzr Studio does not show an OpenTelemetry or OTLP collector URL, ask Lyzr support for the workspace's external OTLP/HTTP traces ingest endpoint and required auth header format.

Use this command only when Lyzr provides a real OTLP endpoint:

```bash
docker compose exec backend python -m backend.app.observability.lyzr_live_trace_check
```

The checker verifies that the configured endpoint accepts OTLP/HTTP traces before reporting a submitted trace id.
