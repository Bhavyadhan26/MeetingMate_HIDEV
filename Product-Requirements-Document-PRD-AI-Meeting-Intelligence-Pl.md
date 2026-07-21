# Product Requirements Document (PRD): AI Meeting Intelligence Platform

**Project:** AI Meeting Intelligence Platform with Organizational Memory  
**Status:** Pre-Launch — Architecture Finalized  
**Version:** 1.0
**Author:** Technical Product Management Team  

---

### 1. Executive Summary
This document outlines the requirements for a system designed to capture, preserve, and audit organizational memory by transforming raw meeting audio into a high-integrity ledger of decisions and actions. Unlike standard transcription tools, this platform acts as an "Organizational Memory Auditor," utilizing a specialized agent swarm to detect contradictions, prevent decision decay, and ensure all commitments are grounded in verbatim evidence while maintaining strict PII compliance.

### 2. Problem Statement
Organizations suffer from "Decision Decay"—commitments made in meetings are frequently forgotten, misinterpreted, or contradicted in subsequent sessions because there is no persistent, active memory. Current solutions provide summaries but lack the "skeptical" auditing required to maintain a consistent source of truth across time and teams.

### 3. Goals & Objectives
*   **Protect the Ledger:** Prevent contradictory decisions from being recorded without explicit acknowledgment.
*   **High-Precision Extraction:** Ensure 100% of recorded decisions are traceable to transcript excerpts.
*   **Privacy-First Intelligence:** Process sensitive organizational data without exposing PII to LLM providers.
*   **Active Recall:** Provide stakeholders with context from past decisions before new meetings begin.

### 4. Target Users / Stakeholders
*   **Project Managers:** To track commitments and prevent scope drift.
*   **Team Leads:** To maintain consistency in decision-making across multiple workstreams.
*   **Compliance Officers:** To ensure a redacted, audited trail of organizational changes.
*   **Individual Contributors:** To query "why" a decision was made months prior.

### 5. Functional Requirements

#### 5.1 Ingestion & Processing
*   **FR-01:** The system shall support raw audio/video ingestion and store files in a Meeting Blob Store (S3/GCS).
*   **FR-02:** The system shall perform Speech-to-Text (STT) and Diarization to produce speaker-tagged transcripts.
*   **FR-03:** The system shall redact PII (names, emails, phones, financials) using stable placeholders (e.g., `[PERSON_1]`) before any text reaches an LLM.

#### 5.2 Specialized Agent Logic
*   **FR-04:** **Summarizer Agent:** Shall generate TL;DRs and key points from redacted transcripts.
*   **FR-05:** **Action Item Extractor:** Shall extract tasks, owners, and deadlines grounded in transcript excerpts.
*   **FR-06:** **Decision Extractor (Conservative Specialist):** Shall prioritize precision over recall, extracting only explicit commitments traceable word-for-word to the transcript. Ambiguous items must be flagged as "Possible Decision."
*   **FR-07:** **Decision Drift Agent (Skeptical Auditor):** Shall compare new decisions against the Qdrant memory ledger. It must classify relationships as:
    *   **New:** No prior decision exists.
    *   **Related:** Touches the same topic but does not conflict.
    *   **Potential Conflict:** Contradicts or reverses a prior active decision without acknowledgment.
*   **FR-08:** **"Related" Classification Behavior:** Decisions classified as "Related" shall be logged silently in the Qdrant ledger and attached as a cross-reference to the new decision's record, visible via the RAG query interface.

#### 5.3 Memory & Recall
*   **FR-09:** **Recall/Query Agent:** Shall provide a natural language interface for querying the organizational memory ledger (Qdrant).
*   **FR-10:** **Pre-Meeting Brief Generator:** Shall proactively query Qdrant for related past decisions before a scheduled meeting starts.

### 6. Non-Functional Requirements
*   **NFR-01:** **System Latency:** Asynchronous processing of a 60-minute meeting must complete within 5 minutes.
*   **NFR-02:** **Scalability:** The system must support concurrent processing of up to 500 meetings per day via Redis/Celery.
*   **NFR-03:** **Reliability:** The system shall utilize exponential backoff for all external API calls (Gemini, Deepgram).
*   **NFR-04:** **Encryption:** All data must be encrypted in transit (TLS 1.3) and at rest (AES-256).
*   **NFR-05:** **Privacy:** No unredacted transcripts shall be persisted in Lyzr traces or sent to LLM providers.

### Traceability Matrix

| Requirement ID | Requirement Summary | Architecture Component(s) | Related Section |
| :--- | :--- | :--- | :--- |
| **FR-01** | Audio/Video Ingestion | Meeting Blob Store / API Gateway | 5.1 |
| **FR-02** | STT & Diarization | STT Service / Infrastructure Layer | 5.1 |
| **FR-03** | PII Redaction | PII Redaction Service (Presidio/SpaCy) | 5.1 |
| **FR-04** | Summarization | ADK Swarm — Summarizer Agent | 5.2 |
| **FR-05** | Action Item Extraction | ADK Swarm — Action Item Extractor | 5.2 |
| **FR-06** | Conservative Extraction | ADK Swarm — Decision Extractor | 5.2 |
| **FR-07** | Conflict Auditing | ADK Swarm — Decision Drift Agent | 5.2 |
| **FR-08** | Related Logging | Memory Layer — Qdrant decisions collection | 5.2 |
| **FR-09** | Memory Querying | ADK Swarm — Recall/Query Agent | 5.3 |
| **FR-10** | Pre-Meeting Briefs | ADK Swarm — Brief Generator | 5.3 |
| **NFR-01** | Processing Latency | Processing Queue (Redis/Celery) | 6.0 |
| **NFR-02** | Scalability | Infrastructure Layer / Redis | 6.0 |
| **NFR-03** | Reliability | Infrastructure Layer / Celery | 6.0 |
| **NFR-04** | Encryption | Encryption Layer (GCP KMS) / Infrastructure | 6.0 |
| **NFR-05** | Privacy/Redaction | PII Redaction Service / Lyzr Studio | 6.0 |

### 7. System Architecture Overview
The system follows a modular, agentic architecture:
1.  **Ingestion Layer:** React frontend and FastAPI gateway handle audio uploads.
2.  **Infrastructure Layer:** Redis/Celery manages async tasks; STT Service generates transcripts.
3.  **Security Shield:** PII Redactor scrubs data before it reaches the ADK Swarm.
4.  **ADK Swarm:** A collection of specialized agents (Summarizer, Extractor, Drift, Recall) orchestrated by an ADK Manager.
5.  **Memory Layer:** Qdrant stores vector embeddings; PostgreSQL stores relational metadata.
6.  **Output Layer:** Notification Service routes alerts; Lyzr Studio provides OTLP observability.

### 8. Tech Stack
*   **Orchestration:** Google ADK (Sequential/Parallel Agent primitives).
*   **LLMs:** Gemini 2.0 Flash (Extraction/Summarization), Gemini 2.0 Pro (Drift Analysis).
*   **Vector Database:** Qdrant.
*   **Relational Database:** PostgreSQL / Supabase.
*   **STT:** Deepgram / OpenAI Whisper.
*   **Privacy:** Microsoft Presidio, SpaCy.
*   **Infrastructure:** Redis, Celery, FastAPI, React.
*   **Observability:** Lyzr Agent Studio (via OpenTelemetry).

**Architectural Commitments Note:**
The core logic and organizational memory of this system are structurally dependent on **Google ADK** and **Qdrant**. Components such as **Lyzr Agent Studio** are swappable for any OTLP-compatible backend without requiring modifications to the underlying agent logic.

### 9. Data Requirements
*   **Qdrant Collections:**
    *   `meeting_chunks`: Embedded transcript segments.
    *   `decisions`: Versioned records (Status: Active, Superseded, Conflicted).
    *   `action_items`: Tasks with metadata.
*   **Data Retention Policy:**
    *   `meeting_chunks` shall be archived to cold storage (S3 Glacier/GCS Archive) after 12 months.
    *   Qdrant search performance is optimized for an entry-count range of 1M to 10M vectors; beyond this, collection sharding will be implemented.
*   **Metadata DB:** Stores RBAC policies, attendee lists, and temporary redaction maps.

### 10. API Specifications
*   `POST /v1/transcripts`: Ingests audio and triggers the async pipeline.
*   `GET /v1/memory/search`: Queries the Recall Agent for past decisions.
*   `POST /v1/decisions/{id}/resolve`: 
    *   **Authorization:** Only the original decider or a user with the "Team Lead" role may resolve a conflict.
    *   **State:** While unresolved, the decision displays a `warning` badge in all RAG queries.
    *   **Timeout:** If no human acts on a Potential Conflict within 48 hours, the decision remains in a `Conflicted` state and is automatically escalated to the Team Lead via a notification digest through the Notification Service. The conflict continues to display the `warning` badge in RAG queries after escalation — escalation does not resolve or dismiss it, only ensures a responsible party is notified.

### 11. Security Requirements
*   **Authentication:** Auth0 integration for JWT-based identity.
*   **RBAC:** Strict siloing of memory by `team_id`.
*   **Encryption Standards:**
    *   TLS 1.3 required for all in-transit communication (Frontend to Gateway, Backend to DBs, Outbound to Gemini/Deepgram).
    *   AES-256 encryption at rest for Qdrant, PostgreSQL, and S3.
    *   Key Management: Cloud provider-managed KMS (GCP KMS). Redaction maps are subject to at-rest encryption while active.

### 12. Deployment & Infrastructure
*   **Containerization:** Dockerized microservices deployed on GKE (Google Kubernetes Engine).
*   **CI/CD:** Automated testing of agent grounding before deployment.
*   **Operational Readiness:**
    *   Target SLA: 99.9% uptime for the API Gateway and Memory Ledger.
    *   Incident Response: PagerDuty rotation for "Severity 1" (Ingestion Blocked) and "Severity 2" (Drift Agent Failure) incidents.

#### 12.1 12-Factor Compliance
*   **Config:** All secrets (Gemini/Deepgram keys) injected via environment variables (GCP Secret Manager).
*   **Dependencies:** Explicitly declared via `poetry.lock` and `package-lock.json`.
*   **Backing Services:** Treated as attached resources (Qdrant, Redis, Postgres).

### 13. Success Metrics & Evaluation

| Metric | Target | Methodology |
| :--- | :--- | :--- |
| **Conflict Precision** | ≥ 90% | Evaluated against a "Golden Set" of 100 synthetic conflict scenarios labeled by senior PMs. |
| **Decision Grounding** | 100% | Automated check: Every decision must contain a `source_excerpt` present in the raw transcript. |
| **User Trust** | ≥ 4/5 Stars | Collected via in-app prompt immediately following a human resolution of a "Potential Conflict." |
| **Decision Recall** | Monitoring Only | Qualitative spot-checks comparing extracted decisions against human-annotated transcripts. |

**Recall Methodology Note:**
Recall is measured qualitatively to monitor the known precision/recall trade-off. A rising volume of "possible_decisions" flags from the Conservative Extractor (FR-06) serves as an early warning signal for recall drift without requiring the extractor to lower its precision threshold.

### 14. Failure Mode Table

| Component | Failure Behavior | User-Visible Impact | Recovery Path |
| :--- | :--- | :--- | :--- |
| **Qdrant** | Connection timeout or 5xx error | Search/memory queries and Drift analysis fail | Redis/Celery retry logic (exponential backoff); "Processing Delayed" status shown in UI |
| **ADK/LLM Provider** | Rate limit or model error | Extraction or Drift analysis stalls | Celery retry logic; fallback to lower-tier model; partial results delivered with "Incomplete" status |
| **PII Redactor** | Service crash | Ingestion blocked | Circuit breaker halts pipeline; admin alert; task remains queued for retry |
| **STT Service** | API failure | Transcript generation fails | Auto-retry via Celery; fallback to "Unattributed" labels; manual upload offered as fallback |

### 15. Timeline & Milestones
*   **Phase 1 (Weeks 1-4):** Ingestion pipeline, STT, and PII Redaction.
*   **Phase 2 (Weeks 5-8):** ADK Swarm development (Extractor & Drift Agent).
*   **Phase 3 (Weeks 9-12):** Qdrant integration, RAG Query Agent, and Slack Notifications.
*   **Phase 4 (Weeks 13+):** Load testing and Production hardening.

### 16. Open Questions & Risks
*   **Cost Risk:** Gemini 2.0 Pro calls for the Drift Agent run on every decision. **Mitigation:** Implement a "Similarity Gate" where the Drift Agent only fires if the initial Qdrant search returns a score > 0.7.