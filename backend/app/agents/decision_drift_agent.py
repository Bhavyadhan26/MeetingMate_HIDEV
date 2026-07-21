from __future__ import annotations

from typing import Any

from backend.app.memory import LocalVectorMemory
from backend.app.models.schemas import Decision, DecisionStatus, DriftClassification, DriftLabel
from backend.app.observability import trace_event

NEGATIONS = ("not ", "no longer", "stop ", "cancel", "reverse", "instead of", "replace", "revert")


class DecisionDriftAgent:
    name = "decision_drift_agent"

    def __init__(self, memory: LocalVectorMemory) -> None:
        self.memory = memory

    def classify(self, decision: Decision, trace_id: str) -> DriftClassification:
        trace_event(self.name, "start", {"trace_id": trace_id, "decision_id": decision.id})
        prior = self.memory.search_decisions(decision.text, decision.team_id, limit=3, status=DecisionStatus.ACTIVE.value)
        if not prior:
            result = DriftClassification(label=DriftLabel.NEW, rationale="No active prior decision was similar enough to compare.")
        else:
            best: Any = prior[0]
            score = float(best.get("score", 0.0))
            new_text = decision.text.lower()
            old_text = str(best.get("text", "")).lower()
            has_reversal = any(term in new_text for term in NEGATIONS) or ("use " in old_text and "do not use" in new_text)
            if score >= 0.35 and has_reversal:
                result = DriftClassification(
                    label=DriftLabel.POTENTIAL_CONFLICT,
                    rationale="New decision appears to reverse or negate a similar active prior decision without explicit resolution.",
                    prior_decision_id=best.get("id"),
                    prior_source_excerpt=best.get("source_excerpt"),
                    score=score,
                )
            elif score >= 0.25:
                result = DriftClassification(
                    label=DriftLabel.RELATED,
                    rationale="A prior decision covers a related topic but the new decision does not explicitly reverse it.",
                    prior_decision_id=best.get("id"),
                    prior_source_excerpt=best.get("source_excerpt"),
                    score=score,
                )
            else:
                result = DriftClassification(label=DriftLabel.NEW, rationale="Nearest prior decision was below the relatedness threshold.", score=score)
        trace_event(self.name, "finish", {"trace_id": trace_id, "label": result.label, "prior": result.prior_decision_id})
        return result

    def write_with_status(self, decision: Decision, trace_id: str) -> Decision:
        drift = self.classify(decision, trace_id)
        decision.drift = drift
        if drift.label == DriftLabel.POTENTIAL_CONFLICT:
            decision.status = DecisionStatus.CONFLICTED
        if drift.prior_decision_id:
            decision.related_decision_ids.append(drift.prior_decision_id)
        self.memory.upsert_decision(decision)
        return decision
