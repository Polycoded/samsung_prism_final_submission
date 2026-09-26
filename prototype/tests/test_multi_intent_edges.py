"""Boundary and scope regressions, including single-intent hard negatives."""
import unittest
from prototype.runtime import LiveRuntime
from prototype.server import TranscriptMessage
from prototype.decomposition import Decomposer
from citefrontier.models import CorpusChunk


class MultiIntentEdges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime = LiveRuntime(backend='lightweight')
        cls.parsers = [runtime.decomposer, Decomposer(runtime.chunks, 'rules')]

    def test_boundaries_and_scope(self):
        cases = [
            ('What receipt and serial number are needed for a LumaPad S1 repair?', ['LumaPad_S1']),
            ('For LumaPad S1, what is the warranty period? What receipt opens a repair?', ['LumaPad_S1']*2),
            ('For LumaPad S1 what is the warranty period; what receipt opens a repair?', ['LumaPad_S1']*2),
            ('For LumaPad S1, warranty period and repair requirements', ['LumaPad_S1']*2),
            ('For LumaPad S1, what is the warranty period and also what receipt opens a repair?', ['LumaPad_S1']*2),
            ('What is the LumaPad S1 warranty and what is the LumaPad S2 battery coverage and where can it be repaired?', ['LumaPad_S1','LumaPad_S2','LumaPad_S2']),
            ('For LumaPad S1, what is the warranty period\nand what receipt opens a repair?', ['LumaPad_S1']*2),
            ('What are the terms and conditions for LumaPad S1?', ['LumaPad_S1']),
            ('For LumaPad S1, what happens between 12 and 24 months?', ['LumaPad_S1']),
            ('For LumaPad S1, what is the warranty and what is the warranty?', ['LumaPad_S1']),
        ]
        for parser in self.parsers:
            for text, expected in cases:
                with self.subTest(parser=parser.method, text=text):
                    result = parser.split(text)
                    self.assertEqual([i.entity_ids for i in result], [(e,) for e in expected])
                    self.assertTrue(all(not i.query.endswith(' and') for i in result))
                    self.assertTrue(all(0 <= a < b <= len(text) for i in result for a,b in i.source_spans))

    def test_first_question_is_not_lost_in_fronted_scope(self):
        for parser in self.parsers:
            intents = parser.split('For LumaPad S1 what is the warranty period; what receipt opens a repair?')
            self.assertIn('warranty', intents[0].topic)
            self.assertIn('receipt', intents[1].topic)

    def test_coordinated_entity_name_is_not_split(self):
        chunk = CorpusChunk('R §Warranty.1', 'R', 'Warranty.1', 'Warranty information.', {'entity': 'Research and Development'})
        parser = Decomposer((chunk,), 'rules')
        self.assertEqual(len(parser.split('What is the warranty for Research and Development?')), 1)

    def test_ambiguous_plural_does_not_choose_last_product(self):
        for parser in self.parsers:
            result = parser.split('What is the warranty for LumaPad S1 and LumaPad S2 and where can they be repaired?')
            self.assertEqual(result[-1].entity_ids, ())


class MultiIntentRuntime(unittest.IsolatedAsyncioTestCase):
    async def test_ambiguous_reference_never_retrieves_without_scope(self):
        runtime = LiveRuntime(backend='lightweight', parser='rules')
        connection = runtime.connection()
        try:
            result = await connection.handle(TranscriptMessage(event_id='e',turn_id='t',timestamp_ms=0,is_final=True,
                text='What is the warranty for LumaPad S1 and LumaPad S2 and where can they be repaired?'))
            self.assertEqual(result['decision'], 'wait')
            self.assertTrue(result['clarification'])
            self.assertEqual(result['stats']['searches'], 0)
            self.assertEqual(result['citations'], [])
        finally:
            await connection.close()

    async def test_sentence_separated_questions_retrieve_both_sources(self):
        runtime = LiveRuntime(backend='lightweight', parser='rules')
        connection = runtime.connection()
        try:
            result = await connection.handle(TranscriptMessage(event_id='e',turn_id='t',timestamp_ms=0,is_final=True,
                text='For LumaPad S1, what is the warranty period? What receipt opens a repair?'))
            self.assertEqual(set(result['citations']), {'LumaPad_S1 §Warranty.1','LumaPad_S1 §Repair.1'})
            self.assertEqual(len(result['claims']), 2)
            self.assertTrue(all(c['citations'][0] in c['candidate_ids'] for c in result['claims']))
        finally:
            await connection.close()


if __name__ == '__main__':
    unittest.main()
