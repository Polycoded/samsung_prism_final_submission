"""Acceptance tests transcribed from the four supplied specification screenshots."""
from __future__ import annotations

import unittest

from citefrontier.models import CorpusChunk
from prototype.runtime import LiveRuntime
from prototype.server import TranscriptMessage


def transcript(text: str, *, event_id: str, turn_id: str = "turn-1",
               timestamp_ms: float, final: bool) -> TranscriptMessage:
    return TranscriptMessage(
        event_id=event_id,
        turn_id=turn_id,
        text=text,
        timestamp_ms=timestamp_ms,
        is_final=final,
    )


def spec_corpus() -> tuple[CorpusChunk, ...]:
    return (
        CorpusChunk(
            "Pune_Workshop §Capacity.1", "Pune_Workshop", "Capacity.1",
            "The Pune workshop venue has capacity for 30 people.",
            {"entity": "Pune workshop venue"},
        ),
        CorpusChunk(
            "Pune_Workshop §Cancellation.1", "Pune_Workshop", "Cancellation.1",
            "The Pune workshop venue cancellation policy permits a documented refund request.",
            {"entity": "Pune workshop venue"},
        ),
        # Catering is deliberately absent: the structured record must expose
        # this as uncertainty rather than fabricate a policy.
        CorpusChunk(
            "Travel_Policy §Standard.1", "Travel_Policy", "Standard.1",
            "The standard employee travel reimbursement rule applies to an employee trip.",
            {"entity": "Travel Policy"},
        ),
        CorpusChunk(
            "Travel_Policy §LateBooking.1", "Travel_Policy", "LateBooking.1",
            "A booking made after travel requires senior director approval.",
            {"entity": "Travel Policy"},
        ),
        CorpusChunk(
            "Travel_Policy §International.1", "Travel_Policy", "International.1",
            "International travel requires mandatory foreign currency receipt verification.",
            {"entity": "Travel Policy"},
        ),
    )


class ScreenshotSpecificationTests(unittest.IsolatedAsyncioTestCase):
    def runtime(self) -> LiveRuntime:
        return LiveRuntime(spec_corpus(), backend="lightweight", parser="rules")

    async def test_example_1_incremental_multi_intent_and_structured_record(self):
        connection = self.runtime().connection()

        first = await connection.handle(transcript(
            "I need to plan a customer workshop in",
            event_id="stream-0", timestamp_ms=0, final=False,
        ))
        self.assertEqual(first["decision"], "wait")
        self.assertEqual(first["stats"]["searches"], 0)

        provisional = await connection.handle(transcript(
            "I need to plan a customer workshop in Pune for 30 people",
            event_id="stream-1", timestamp_ms=800, final=False,
        ))
        self.assertEqual(provisional["decision"], "provisional_retrieve")
        self.assertGreaterEqual(provisional["stats"]["searches"], 1)
        self.assertEqual(provisional["claims"], [])

        final = await connection.handle(transcript(
            "For Pune workshop venue, what is the capacity for 30 people; "
            "what is the cancellation policy; what are the catering options?",
            event_id="stream-2", timestamp_ms=1600, final=True,
        ))
        self.assertEqual(final["decision"], "commit_retrieve")
        self.assertEqual(len(final["sub_queries"]), 3)
        self.assertEqual(len(final["claims"]), 3)
        self.assertIn("Pune_Workshop §Capacity.1", final["citations"])
        self.assertIn("Pune_Workshop §Cancellation.1", final["citations"])
        self.assertTrue(any("catering" in text.lower() for text in final["uncertainty"]))

        starts = [e for e in connection.telemetry if e["event_type"] == "retrieval_started"]
        final_starts = [e for e in starts if e["payload"]["trigger"] == "final_commit"]
        self.assertEqual(len(final_starts), 3)
        self.assertTrue(all(e["timestamp_s"] == 1.6 for e in final_starts))
        self.assertTrue(all(e["token_cost"]["estimated_usd"] == 0 for e in connection.telemetry))

    async def test_example_2_late_detail_refines_without_restart(self):
        connection = self.runtime().connection()
        initial = await connection.handle(transcript(
            "Summarize the Travel Policy reimbursement rule for an employee trip.",
            event_id="travel-1", timestamp_ms=0, final=True,
        ))
        self.assertEqual(initial["answer_version"], 1)
        self.assertIn("Travel_Policy §Standard.1", initial["citations"])
        initial_claim_id = initial["claims"][0]["claim_id"]

        refined = await connection.handle(transcript(
            "The trip was international and the booking was made after travel.",
            event_id="travel-2", turn_id="turn-2", timestamp_ms=1200, final=True,
        ))
        self.assertEqual(refined["reason"], "targeted_delta")
        self.assertEqual(refined["answer_version"], 2)
        self.assertIn(initial_claim_id, {c["claim_id"] for c in refined["claims"]})
        self.assertIn("Travel_Policy §International.1", refined["citations"])
        self.assertIn("Travel_Policy §LateBooking.1", refined["citations"])
        patch = refined["history"][-1]
        self.assertNotIn(initial_claim_id, patch["removed"])

    async def test_example_3_presentation_request_suppresses_retrieval(self):
        connection = self.runtime().connection()
        initial = await connection.handle(transcript(
            "Summarize the Travel Policy reimbursement rule for an employee trip.",
            event_id="format-1", timestamp_ms=0, final=True,
        ))
        formatted = await connection.handle(transcript(
            "Please repeat your last answer in two bullets.",
            event_id="format-2", turn_id="turn-2", timestamp_ms=1000, final=True,
        ))
        self.assertEqual(formatted["decision"], "suppress")
        self.assertEqual(formatted["reason"], "presentation_only")
        self.assertEqual(formatted["stats"], initial["stats"])
        self.assertEqual(formatted["claims"], initial["claims"])
        self.assertEqual(formatted["citations"], initial["citations"])
        self.assertEqual(formatted["answer_version"], initial["answer_version"])
        self.assertFalse(any(
            e["event_type"] == "retrieval_started"
            for e in formatted["retrieval_events"]
        ))


if __name__ == "__main__":
    unittest.main()
