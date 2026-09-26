"""Replay evaluation for disclosed Streaming Live RAG acceptance signals.

The official replay format is not available, so this module defines a small,
public schema for local development. It computes auditable proxies and never
claims the official gates have passed until run against their held-out corpus.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Iterable

from .engine import CiteFrontierEngine
from .grounding import ClaimEvidenceSelector
from .models import EngineOutput, TranscriptEvent
from .retrieval import HybridRetriever
from .text import split_intents


@dataclass(frozen=True)
class ReplayExpectation:
    eligible_for_early_retrieval: bool = False
    minimum_subintents: int = 1
    allowed_citations: tuple[str, ...] = ()
    no_retrieval_required: bool = False


@dataclass(frozen=True)
class ReplayCase:
    case_id: str
    events: tuple[TranscriptEvent, ...]
    expectation: ReplayExpectation
    prior_user_turns: tuple[str, ...] = ()


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    early_retrieval_before_endpoint: bool | None
    multi_intent_correct: bool | None
    endpoint_evidence_hit_at_5: bool | None
    citation_support_proxy: bool
    no_retrieval_false_trigger: bool
    telemetry_complete: bool


@dataclass(frozen=True)
class EvaluationReport:
    cases: tuple[CaseScore, ...]
    early_retrieval_rate: float | None
    multi_intent_rate: float | None
    endpoint_evidence_hit_at_5_rate: float | None
    citation_support_rate: float
    no_retrieval_false_trigger_rate: float | None
    telemetry_coverage_rate: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _telemetry_complete(engine: CiteFrontierEngine, session_id: str, event_count: int) -> bool:
    controllers = [
        event for event in engine.telemetry.by_type("controller_decision") if event.session_id == session_id
    ]
    if len(controllers) < event_count:
        return False
    for event in controllers:
        if not {"decision", "reason", "intents", "token_cost_estimate"}.issubset(event.payload):
            return False
    for event in engine.telemetry.by_type("retrieval_started"):
        if event.session_id != session_id:
            continue
        if not {
            "retrieval_event_id",
            "trigger",
            "query",
            "candidate_chunk_ids",
            "coverage",
            "graph_expanded",
        }.issubset(event.payload):
            return False
    for event in engine.telemetry.by_type("answer_version"):
        if event.session_id != session_id:
            continue
        if not {"version", "parent_version", "changed_claim_ids", "citations"}.issubset(event.payload):
            return False
    return True


def _mean_or_none(values: list[bool]) -> float | None:
    return mean(values) if values else None


def evaluate_cases(
    cases: Iterable[ReplayCase],
    retriever: HybridRetriever,
    use_dialogue_context: bool = False,
    claim_evidence_selector: ClaimEvidenceSelector | None = None,
) -> EvaluationReport:
    """Run local cases and return only observable, reproducible measurements."""

    cases = tuple(cases)
    results: list[CaseScore] = []
    for case in cases:
        if not case.events:
            raise ValueError(f"Replay case {case.case_id} has no transcript events")
        engine = CiteFrontierEngine(
            retriever,
            use_dialogue_context=use_dialogue_context,
            claim_evidence_selector=claim_evidence_selector,
        )
        session = engine.new_session()
        # The history is user-provided dialogue text only. It models the
        # ephemeral state that a live session would have collected before this
        # turn, without leaking benchmark response labels or agent text.
        for prior_turn in case.prior_user_turns:
            session.remember_committed_turn(split_intents(prior_turn))
        outputs: list[EngineOutput] = [engine.process_stream(session, event) for event in case.events]
        final_event = next((event for event in reversed(case.events) if event.is_final), case.events[-1])
        retrievals = engine.telemetry.by_type("retrieval_started")
        early = any(event.timestamp_s < final_event.timestamp_s and event.payload["trigger"] == "provisional" for event in retrievals)
        final_output = outputs[-1]
        detected = len(final_output.action.intents)
        final_citations = {
            citation
            for claim in (session.latest.claims if session.latest else ())
            for citation in claim.citations
        }
        citation_proxy = (
            bool(final_citations) and final_citations.issubset(set(case.expectation.allowed_citations))
            if case.expectation.allowed_citations
            else True
        )
        endpoint_candidate_ids = {
            chunk_id
            for retrieval in retrievals
            if retrieval.payload["trigger"] == "endpoint_commit"
            for chunk_id in retrieval.payload["candidate_chunk_ids"]
        }
        endpoint_hit = (
            bool(endpoint_candidate_ids & set(case.expectation.allowed_citations))
            if case.expectation.allowed_citations
            else None
        )
        results.append(
            CaseScore(
                case_id=case.case_id,
                early_retrieval_before_endpoint=(early if case.expectation.eligible_for_early_retrieval else None),
                multi_intent_correct=(
                    detected >= case.expectation.minimum_subintents
                    if case.expectation.minimum_subintents >= 2
                    else None
                ),
                endpoint_evidence_hit_at_5=endpoint_hit,
                citation_support_proxy=citation_proxy,
                no_retrieval_false_trigger=(
                    bool(retrievals) if case.expectation.no_retrieval_required else False
                ),
                telemetry_complete=_telemetry_complete(engine, session.session_id, len(case.events)),
            )
        )

    eligible = [score.early_retrieval_before_endpoint for score in results if score.early_retrieval_before_endpoint is not None]
    compound = [score.multi_intent_correct for score in results if score.multi_intent_correct is not None]
    endpoint_hits = [score.endpoint_evidence_hit_at_5 for score in results if score.endpoint_evidence_hit_at_5 is not None]
    no_retrieval_expected = [
        score.no_retrieval_false_trigger
        for score, case in zip(results, cases, strict=True)
        if case.expectation.no_retrieval_required
    ]
    return EvaluationReport(
        cases=tuple(results),
        early_retrieval_rate=_mean_or_none([value for value in eligible if value is not None]),
        multi_intent_rate=_mean_or_none([value for value in compound if value is not None]),
        endpoint_evidence_hit_at_5_rate=_mean_or_none([value for value in endpoint_hits if value is not None]),
        citation_support_rate=mean([score.citation_support_proxy for score in results]) if results else 0.0,
        no_retrieval_false_trigger_rate=(mean(no_retrieval_expected) if no_retrieval_expected else None),
        telemetry_coverage_rate=mean([score.telemetry_complete for score in results]) if results else 0.0,
    )
