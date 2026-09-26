import asyncio
import unittest
from prototype.benchmark import run_benchmark, validate_cases
from prototype.runtime import LiveRuntime
from prototype.upload import parse_upload


class OrganizerBenchmarkTests(unittest.TestCase):
    def test_session_corpus_benchmark_reports_pass_fail_and_grounding(self):
        chunks = parse_upload([{"name": "Hall.md", "text": "## Capacity.1\nHall capacity is 80 people."}])
        cases = [
            {"id": "supported", "question": "Hall capacity", "expected_citations": ["Hall §Capacity.1"]},
            {"id": "unsupported", "question": "Does Hall support teleportation?", "expected_citations": [], "unsupported": True},
        ]
        result = asyncio.run(run_benchmark(LiveRuntime(chunks=chunks), cases))
        self.assertEqual((result["passed"], result["total"]), (2, 2))
        self.assertEqual(result["fabricated_ids"], 0)
        self.assertEqual(result["citation_support"]["supported"], result["citation_support"]["emitted"])

    def test_rejects_unlabeled_or_oversized_benchmarks(self):
        for cases in ([], [{}], [{"question": "x"}] * 51):
            with self.subTest(cases=len(cases)), self.assertRaises(ValueError):
                validate_cases(cases)


if __name__ == "__main__":
    unittest.main()
