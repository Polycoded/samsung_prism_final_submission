from __future__ import annotations

import unittest

from citefrontier.evaluation import ReplayCase, ReplayExpectation, evaluate_cases
from citefrontier.fixtures import fixture_retriever, multi_intent_trace
from citefrontier.models import TranscriptEvent


class ReplayEvaluationTests(unittest.TestCase):
    def test_local_replay_reports_observable_gate_proxies(self) -> None:
        cases = (
            ReplayCase(
                "compound-early",
                multi_intent_trace(),
                ReplayExpectation(
                    eligible_for_early_retrieval=True,
                    minimum_subintents=3,
                    allowed_citations=("Doc_Venue §1", "Doc_Cancellation §2", "Doc_Catering §1"),
                ),
            ),
            ReplayCase(
                "no-content",
                (TranscriptEvent(0.0, "hi", is_final=True),),
                ReplayExpectation(no_retrieval_required=True),
            ),
        )
        report = evaluate_cases(cases, fixture_retriever())
        self.assertEqual(report.early_retrieval_rate, 1.0)
        self.assertEqual(report.multi_intent_rate, 1.0)
        self.assertEqual(report.citation_support_rate, 1.0)
        self.assertEqual(report.no_retrieval_false_trigger_rate, 0.0)
        self.assertEqual(report.telemetry_coverage_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
