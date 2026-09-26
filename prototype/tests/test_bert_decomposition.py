import unittest

from prototype.bert_decomposition import (
    BoundaryPrediction,
    BoundarySpan,
    HybridDecomposer,
)
from prototype.runtime import LiveRuntime


class FakeDetector:
    def __init__(self, spans=(), valid=True, reason=None):
        self.spans = spans
        self.valid = valid
        self.reason = reason

    def predict(self, text):
        values = tuple(BoundarySpan(a, b, confidence, text[a:b]) for a, b, confidence in self.spans)
        return BoundaryPrediction(values, (), (), 1.25, self.valid, self.reason)


class BertDecompositionTests(unittest.TestCase):
    def test_fronted_scope_with_question_is_not_dropped(self):
        detector = FakeDetector(spans=((0, 42, .999), (47, 77, .999), (82, 115, .999)))
        parser = HybridDecomposer(self.chunks, 'auto', detector=detector)
        text = 'for LumaPad S1 what is the warranty period and what liquid damage is excluded and what receipt do I need for repair'
        intents = parser.split(text)
        self.assertEqual(len(intents), 3)
        self.assertIn('warranty', intents[0].topic)

    @classmethod
    def setUpClass(cls):
        cls.chunks = LiveRuntime(backend="lightweight").chunks

    def hybrid(self, mode, detector, threshold=.90):
        return HybridDecomposer(
            self.chunks, mode, fallback_parser="rules",
            detector=detector, threshold=threshold,
        )

    def test_auto_accepts_valid_confident_spans_and_enriches_intents(self):
        text = "For LumaPad S1, what is the warranty and what receipt opens a repair?"
        first = text.index("what")
        split = text.index(" and what")
        second = split + len(" and ")
        decomposer = self.hybrid("auto", FakeDetector(((first, split, .99), (second, len(text), .98))))
        intents = decomposer.split(text)
        self.assertEqual(len(intents), 2)
        self.assertTrue(all(i.method == "bert_intent_boundary" for i in intents))
        self.assertTrue(all(i.entity_ids == ("LumaPad_S1",) for i in intents))
        self.assertEqual(intents[0].source_spans, ((first, split),))
        diagnostic = decomposer.consume_diagnostic()
        self.assertEqual(diagnostic["served"], "bert")
        self.assertTrue(diagnostic["accepted"])

    def test_shadow_serves_rules_and_logs_disagreement(self):
        text = "For LumaPad S1, what is the warranty and what receipt opens a repair?"
        detector = FakeDetector(((0, len(text), .99),))
        decomposer = self.hybrid("shadow", detector)
        served = decomposer.split(text)
        self.assertEqual(len(served), 2)
        diagnostic = decomposer.consume_diagnostic()
        self.assertEqual(diagnostic["served"], "rules")
        self.assertFalse(diagnostic["agreement"])

    def test_invalid_prediction_falls_back_to_rules(self):
        text = "For LumaPad S1, what is the warranty and what receipt opens a repair?"
        decomposer = self.hybrid("auto", FakeDetector(valid=False, reason="invalid_transition"))
        served = decomposer.split(text)
        self.assertEqual(len(served), 2)
        diagnostic = decomposer.consume_diagnostic()
        self.assertEqual(diagnostic["served"], "rules")
        self.assertIn("invalid_transition", diagnostic["fallback_reason"])

    def test_low_confidence_prediction_falls_back_to_rules(self):
        text = "LumaPad S1 warranty period"
        decomposer = self.hybrid("auto", FakeDetector(((0, len(text), .50),)))
        served = decomposer.split(text)
        self.assertEqual(len(served), 1)
        self.assertEqual(decomposer.consume_diagnostic()["fallback_reason"], "confidence_below_threshold")


if __name__ == "__main__":
    unittest.main()
