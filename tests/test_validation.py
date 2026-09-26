from __future__ import annotations

import unittest

from citefrontier.engine import CiteFrontierEngine
from citefrontier.fixtures import fixture_retriever, multi_intent_trace
from citefrontier.models import Decision, TranscriptEvent
from citefrontier.validation import run


class CiteFrontierValidationTests(unittest.TestCase):
    def test_fixture_validation_invariants(self) -> None:
        result = run()
        self.assertTrue(result["early_retrieval_before_endpoint"])
        self.assertTrue(result["multi_intent_detected"])
        self.assertEqual(result["delta_refinement_version"], 2)
        self.assertTrue(result["unaffected_claim_preserved"])
        self.assertTrue(result["presentation_query_suppressed"])
        self.assertTrue(result["late_detail_uses_one_targeted_retrieval"])
        self.assertTrue(result["all_final_citations_committed"])

    def test_provisional_evidence_never_enters_final_citations(self) -> None:
        engine = CiteFrontierEngine(fixture_retriever())
        session = engine.new_session()
        outputs = [engine.process_stream(session, event) for event in multi_intent_trace()]
        provisional_ids = set(outputs[1].retrieval_event_ids + outputs[2].retrieval_event_ids)
        final = session.latest
        self.assertIsNotNone(final)
        final_event_ids = {event_id for claim in final.claims for event_id in claim.evidence_event_ids}
        self.assertTrue(final_event_ids.isdisjoint(provisional_ids))

    def test_correction_invalidates_provisional_event_before_final_answer(self) -> None:
        engine = CiteFrontierEngine(fixture_retriever())
        session = engine.new_session()
        engine.process_stream(session, TranscriptEvent(0.0, "Find warranty details for"))
        provisional = engine.process_stream(session, TranscriptEvent(0.8, "Find warranty details for Model A device coverage"))
        final = engine.process_stream(
            session,
            TranscriptEvent(1.2, "Find warranty details for Model A device coverage actually Model B instead", is_final=True),
        )
        self.assertEqual(provisional.action.decision, Decision.PROVISIONAL_RETRIEVE)
        self.assertTrue(session.invalidated_provisionals)
        provisional_ids = set(provisional.retrieval_event_ids)
        final_event_ids = {event_id for claim in final.answer.claims for event_id in claim.evidence_event_ids}
        self.assertTrue(final_event_ids.isdisjoint(provisional_ids))

    def test_graph_expansion_is_visible_in_telemetry(self) -> None:
        engine = CiteFrontierEngine(fixture_retriever())
        session = engine.new_session()
        engine.process_stream(session, TranscriptEvent(0.0, "Summarize employee reimbursement", is_final=True))
        retrievals = engine.telemetry.by_type("retrieval_started")
        self.assertTrue(any(event.payload["graph_expanded"] for event in retrievals))

    def test_missing_evidence_emits_uncertainty_without_a_citation(self) -> None:
        engine = CiteFrontierEngine(fixture_retriever())
        session = engine.new_session()
        output = engine.process_stream(
            session,
            TranscriptEvent(0.0, "What is the lunar warranty exception", is_final=True),
        )
        self.assertEqual(len(output.answer.claims), 1)
        claim = output.answer.claims[0]
        self.assertEqual(claim.citations, ())
        self.assertTrue(claim.text.startswith("I could not verify:"))

    def test_elliptical_followup_uses_ephemeral_user_intent_context_only(self) -> None:
        engine = CiteFrontierEngine(fixture_retriever(), use_dialogue_context=True)
        session = engine.new_session()
        engine.process_stream(
            session,
            TranscriptEvent(0.0, "Tell me the warranty coverage for Model B device", is_final=True),
        )
        engine.begin_turn(session)
        output = engine.process_stream(session, TranscriptEvent(1.0, "What about that?", is_final=True))

        retrieval = engine.telemetry.by_type("retrieval_started")[-1]
        self.assertTrue(retrieval.payload["contextualization_used"])
        self.assertEqual(retrieval.payload["user_query"], "about that")
        self.assertEqual(retrieval.payload["query"], "tell warranty coverage model b device")
        self.assertEqual(output.answer.claims[-1].citations, ("Doc_Warranty_B §1",))

        isolated_session = engine.new_session()
        engine.process_stream(engine.new_session(), TranscriptEvent(2.0, "irrelevant", is_final=True))
        engine.begin_turn(isolated_session)
        isolated = engine.process_stream(isolated_session, TranscriptEvent(3.0, "What about that?", is_final=True))
        isolated_retrieval = engine.telemetry.by_type("retrieval_started")[-1]
        self.assertFalse(isolated_retrieval.payload["contextualization_used"])
        self.assertEqual(isolated.answer.claims[0].citations, ())


if __name__ == "__main__":
    unittest.main()
