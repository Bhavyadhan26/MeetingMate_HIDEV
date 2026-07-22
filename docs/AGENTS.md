# Agents

## Manager

File: `backend/app/agents/manager.py`

Input: `Meeting`, `Transcript`  
Output: `ProcessingResult`

The manager uses `backend/app/agents/adk_runtime.py` when `google-adk` is installed. The ADK graph is:

```text
SequentialAgent: meeting_intelligence_adk_manager
  ParallelAgent: parallel_extraction_swarm
    summarizer_adk_agent
    action_item_extractor_adk_agent
    decision_extractor_adk_agent
```

The ADK graph performs parallel extraction for summary, action items, and decisions. The Python manager then sequentially runs drift classification because drift depends on extracted decisions and Qdrant memory state. If `google-adk` is unavailable, the same business agents run through a threaded fallback so local tests do not require cloud dependencies.

## Summarizer Agent

File: `backend/app/agents/summarizer.py`

Produces a short TL;DR and key points from the redacted transcript.

ADK wrapper name: `summarizer_adk_agent`

## Action Item Extractor

File: `backend/app/agents/action_item_extractor.py`

Extracts owner, task, deadline, and source excerpt. Every action item must include the exact transcript sentence that grounded it.

ADK wrapper name: `action_item_extractor_adk_agent`

## Conservative Decision Extractor

File: `backend/app/agents/decision_extractor.py`

Extracts only explicit commitments using phrases such as `we decided`, `we agreed`, `we approved`, or `Decision:`. Ambiguous language such as `maybe`, `consider`, or `proposal` is emitted as `possible_decisions`.

ADK wrapper name: `decision_extractor_adk_agent`

## Decision Drift Agent

File: `backend/app/agents/decision_drift_agent.py`

Labels:
- `New`: no active prior decision clears the relatedness threshold.
- `Related`: a similar prior decision exists but the new text does not explicitly reverse it.
- `Potential Conflict`: a similar active prior decision exists and the new decision uses reversal or negation language such as `no longer`, `stop`, `cancel`, `reverse`, `replace`, or `revert`.

Potential conflicts are written as `status=conflicted` and include the prior decision id.

Acknowledged replacements complete the `superseded` lifecycle. If the new decision explicitly says it supersedes, replaces, resolves, or overrides the prior decision, the new decision is written as `status=active`, the prior active decision is updated to `status=superseded`, and the new decision keeps the prior id in `related_decision_ids`. Unacknowledged reversals remain `status=conflicted` until human review.

Conflict resolution is human-gated through `/v1/decisions/{id}/resolve`. The MVP role check allows `team_lead`, `decision_owner`, and `admin` by default through `CONFLICT_RESOLVER_ROLES`; other roles receive `authorization_failed`. Unresolved conflicts are auditable through `/v1/decisions/conflicts`, which marks conflicts older than `CONFLICT_ESCALATION_HOURS` and emits a `conflict_resolution.escalated` trace event for follow-up.

## Recall Agent

File: `backend/app/agents/recall_agent.py`

Embeds the query, searches memory, and returns a grounded answer with decision citations and source excerpts.

The same agent generates pre-meeting briefs through `/v1/briefs/pre-meeting`: each agenda topic is embedded, matched against prior team decisions, and returned with cited source excerpts so the brief can be inspected rather than trusted as free-form prose.
