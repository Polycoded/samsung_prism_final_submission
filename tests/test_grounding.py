from __future__ import annotations

import unittest

from citefrontier.engine import CiteFrontierEngine
from citefrontier.fixtures import fixture_retriever
from citefrontier.grounding import (
    CitationCandidateGuard,
    ClaimEvidenceSelector,
    EntailmentResult,
)
from citefrontier.models import CorpusChunk, Evidence, TranscriptEvent


class RejectingVerifier:
    def verify(self, claim: str, evidence_text: str) -> EntailmentResult:
        return EntailmentResult(False, 0.01, "contradiction")


class SupportingVerifier:
    def verify(self, claim: str, evidence_text: str) -> EntailmentResult:
        return EntailmentResult(evidence_text == "supported", 0.91, "entailment")


def _evidence(chunk_id: str, text: str) -> Evidence:
    return Evidence(
        chunk=CorpusChunk(chunk_id, "Doc", "1", text),
        score=0.5,
        coverage=1.0,
        origin="reranked",
        retrieval_event_id="retrieval-1",
    )


class GroundingTests(unittest.TestCase):
    def test_selector_emits_only_verified_current_candidate(self) -> None:
        first = _evidence("Doc §1", "not supported")
        second = _evidence("Doc §2", "supported")
        selection = ClaimEvidenceSelector(SupportingVerifier()).select("claim", (first, second))

        self.assertEqual(selection.evidence, second)
        self.assertEqual(selection.evaluated_candidate_ids, ("Doc §1", "Doc §2"))
        self.assertTrue(selection.verification.entailed)

    def test_citation_guard_strips_ids_outside_current_candidates(self) -> None:
        decision = CitationCandidateGuard().enforce(
            ("Doc §1", "invented §99"),
            (_evidence("Doc §1", "supported"),),
        )

        self.assertEqual(decision.accepted_citation_ids, ("Doc §1",))
        self.assertEqual(decision.rejected_citation_ids, ("invented §99",))

    def test_rejected_claim_becomes_uncertainty_before_synthesis(self) -> None:
        engine = CiteFrontierEngine(
            fixture_retriever(),
            claim_evidence_selector=ClaimEvidenceSelector(RejectingVerifier()),
        )
        session = engine.new_session()
        output = engine.process_stream(
            session,
            TranscriptEvent(0.0, "Tell me warranty coverage for Model B", is_final=True),
        )

        claim = output.answer.claims[0]
        selection = engine.telemetry.by_type("claim_evidence_selected")[-1]
        self.assertEqual(claim.citations, ())
        self.assertTrue(claim.text.startswith("I could not verify:"))
        self.assertNotIn("[]", output.rendered_answer)
        self.assertTrue(selection.payload["uncertainty_required"])
        self.assertIsNone(selection.payload["selected_chunk_id"])


if __name__ == "__main__":
    unittest.main()
