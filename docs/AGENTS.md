# Agents

## Manager

File: `backend/app/agents/manager.py`

Input: `Meeting`, `Transcript`  
Output: `ProcessingResult`

The manager performs parallel extraction for summary, action items, and decisions, then sequentially runs drift classification because drift depends on extracted decisions.

## Summarizer Agent

File: `backend/app/agents/summarizer.py`

Produces a short TL;DR and key points from the redacted transcript.

## Action Item Extractor

File: `backend/app/agents/action_item_extractor.py`

Extracts owner, task, deadline, and source excerpt. Every action item must include the exact transcript sentence that grounded it.

## Conservative Decision Extractor

File: `backend/app/agents/decision_extractor.py`

Extracts only explicit commitments using phrases such as `we decided`, `we agreed`, `we approved`, or `Decision:`. Ambiguous language such as `maybe`, `consider`, or `proposal` is emitted as `possible_decisions`.

## Decision Drift Agent

File: `backend/app/agents/decision_drift_agent.py`

Labels:
- `New`: no active prior decision clears the relatedness threshold.
- `Related`: a similar prior decision exists but the new text does not explicitly reverse it.
- `Potential Conflict`: a similar active prior decision exists and the new decision uses reversal or negation language such as `no longer`, `stop`, `cancel`, `reverse`, `replace`, or `revert`.

Potential conflicts are written as `status=conflicted` and include the prior decision id.

## Recall Agent

File: `backend/app/agents/recall_agent.py`

Embeds the query, searches memory, and returns a grounded answer with decision citations and source excerpts.
