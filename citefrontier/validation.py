"""Executable raw-result validation for the disclosed fixture scenarios."""

from __future__ import annotations

import json

from .engine import CiteFrontierEngine
from .fixtures import fixture_retriever, multi_intent_trace
from .models import TranscriptEvent


def run() -> dict[str, object]:
    engine = CiteFrontierEngine(fixture_retriever())
    multi_session = engine.new_session()
    outputs = [engine.process_stream(multi_session, event) for event in multi_intent_trace()]
    early = outputs[1].action.decision.value == "provisional_retrieve"
    multi_intent = len(outputs[-1].action.intents) >= 2

    travel_session = engine.new_session()
    initial = engine.process_stream(
        travel_session,
        TranscriptEvent(0.0, "Summarize travel reimbursement rule and catering policy", is_final=True),
    )
    target = next(claim.intent_key for claim in initial.answer.claims if "travel" in claim.intent_key)
    unchanged = next(claim for claim in initial.answer.claims if "catering" in claim.intent_key)
    refined = engine.refine_with_late_detail(
        travel_session,
        1.0,
        target,
        "The trip was international and the booking was made after travel",
    )
    unchanged_after = next(claim for claim in refined.answer.claims if "catering" in claim.intent_key)
    suppression = engine.process_stream(
        travel_session,
        TranscriptEvent(1.2, "Please repeat my last answer in two bullets"),
    )

    result = {
        "early_retrieval_before_endpoint": early,
        "multi_intent_detected": multi_intent,
        "delta_refinement_version": refined.answer.version,
        "unaffected_claim_preserved": unchanged.claim_id == unchanged_after.claim_id,
        "presentation_query_suppressed": suppression.action.decision.value == "suppress" and not suppression.retrieval_event_ids,
        "late_detail_uses_one_targeted_retrieval": len(refined.retrieval_event_ids) == 1,
        "trace_event_count": len(engine.telemetry.events),
        "all_final_citations_committed": all(
            evidence_id.startswith("retrieval-")
            for answer in (multi_session.latest, travel_session.latest)
            for claim in answer.claims
            for evidence_id in claim.evidence_event_ids
        ),
    }
    return result


def main() -> None:
    print(json.dumps(run(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
