from __future__ import annotations

from typing import Any

from backend.app.memory import LocalVectorMemory
from backend.app.models.schemas import Decision, DecisionStatus, DriftClassification, DriftLabel
from backend.app.observability import trace_event
from backend.app.agents.groq_llm import chat_json, groq_enabled

NEGATIONS = ("not ", "no longer", "stop ", "cancel", "reverse", "instead of", "replace", "revert")
SUPERSESSION_TERMS = (
    "supersede",
    "supersedes",
    "superseded",
    "replace the prior",
    "replace prior",
    "replaces the prior",
    "resolve the prior",
    "resolves the prior",
    "override the prior",
    "overrides the prior",
 )


class DecisionDriftAgent:
    name = "decision_drift_agent"

    def __init__(self, memory: LocalVectorMemory) -> None:
        self.memory = memory

    def classify(self, decision: Decision, trace_id: str) -> DriftClassification:
        trace_event(self.name, "start", {"trace_id": trace_id, "decision_id": decision.id})
        prior = self.memory.search_decisions(decision.text, decision.team_id, limit=3, status=DecisionStatus.ACTIVE.value)
        if not prior:
            result = DriftClassification(label=DriftLabel.NEW, rationale="No active prior decision was similar enough to compare.")
        elif groq_enabled():
            try:
                result = self._classify_with_groq(decision, prior)
            except Exception as exc:
                trace_event(self.name, "groq_error", {"trace_id": trace_id, "error": str(exc)})
                result = self._classify_deterministic(decision, prior)
        else:
            result = self._classify_deterministic(decision, prior)
        trace_event(self.name, "finish", {"trace_id": trace_id, "label": result.label, "prior": result.prior_decision_id})
        return result

    def _classify_with_groq(self, decision: Decision, prior: list[dict[str, Any]]) -> DriftClassification:
        payload = chat_json(
            "Classify decision drift. Return JSON with label exactly one of New, Related, Potential Conflict; rationale; prior_decision_id; prior_source_excerpt; score. Potential Conflict means the new explicit decision contradicts or reverses an active prior decision without saying it resolves it.",
            f"New decision: {decision.text}\nPrior active decisions JSON:\n{prior}",
            max_tokens=900,
        )
        label = str(payload.get("label") or "New")
        if label not in {item.value for item in DriftLabel}:
            label = DriftLabel.NEW.value
        return DriftClassification(
            label=DriftLabel(label),
            rationale=str(payload.get("rationale") or "Classified by Groq."),
            prior_decision_id=payload.get("prior_decision_id"),
            prior_source_excerpt=payload.get("prior_source_excerpt"),
            score=float(payload.get("score") or float(prior[0].get("score", 0.0))),
        )

    def _classify_deterministic(self, decision: Decision, prior: list[dict[str, Any]]) -> DriftClassification:
        best: Any = prior[0]
        score = float(best.get("score", 0.0))
        new_text = decision.text.lower()
        old_text = str(best.get("text", "")).lower()
        has_reversal = any(term in new_text for term in NEGATIONS) or ("use " in old_text and "do not use" in new_text)
        if score >= 0.35 and has_reversal:
            return DriftClassification(
                label=DriftLabel.POTENTIAL_CONFLICT,
                rationale="New decision appears to reverse or negate a similar active prior decision without explicit resolution.",
                prior_decision_id=best.get("id"),
                prior_source_excerpt=best.get("source_excerpt"),
                score=score,
            )
        if score >= 0.25:
            return DriftClassification(
                label=DriftLabel.RELATED,
                rationale="A prior decision covers a related topic but the new decision does not explicitly reverse it.",
                prior_decision_id=best.get("id"),
                prior_source_excerpt=best.get("source_excerpt"),
                score=score,
            )
        return DriftClassification(label=DriftLabel.NEW, rationale="Nearest prior decision was below the relatedness threshold.", score=score)

    def write_with_status(self, decision: Decision, trace_id: str) -> Decision:
        drift = self.classify(decision, trace_id)
        decision.drift = drift
        supersedes_prior = bool(drift.prior_decision_id and self._acknowledges_supersession(decision.text))
        if supersedes_prior:
            self.memory.update_decision(drift.prior_decision_id, status=DecisionStatus.SUPERSEDED.value)
            decision.status = DecisionStatus.ACTIVE
            trace_event(
                self.name,
                "superseded_prior",
                {"trace_id": trace_id, "decision_id": decision.id, "prior_decision_id": drift.prior_decision_id},
            )
        elif drift.label == DriftLabel.POTENTIAL_CONFLICT:
            decision.status = DecisionStatus.CONFLICTED
        if drift.prior_decision_id:
            decision.related_decision_ids.append(drift.prior_decision_id)
        self.memory.upsert_decision(decision)
        return decision

    def _acknowledges_supersession(self, text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in SUPERSESSION_TERMS)
