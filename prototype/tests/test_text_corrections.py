import unittest

from prototype.runtime import LiveRuntime
from prototype.server import TranscriptMessage
from prototype.transcript import normalize_correction, normalize_disfluencies


class TextCorrections(unittest.IsolatedAsyncioTestCase):
    def test_fillers_and_immediate_repetitions_are_transparently_removed(self):
        cleaned, changes = normalize_disfluencies('umm what what is uh the LumaPad S1 warranty')
        self.assertEqual(cleaned, 'what is the LumaPad S1 warranty')
        self.assertEqual([item['type'] for item in changes], ['filler', 'filler', 'repetition'])

    def test_numeric_correction_markers_replace_only_the_local_value(self):
        aliases = {}
        cases = {
            'The room is for 6—sorry, 7 people and what is parking like?':
                'The room is for 7 people and what is parking like?',
            'The room is for 6, make that 7 people': 'The room is for 7 people',
            'The room is for 6, I mean 7 people': 'The room is for 7 people',
            'The room is for 6, no, 7 people': 'The room is for 7 people',
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                normalized, change, ambiguous = normalize_correction(raw, aliases)
                self.assertEqual(normalized, expected)
                self.assertEqual(change['from'], '6')
                self.assertEqual(change['to'], '7')
                self.assertFalse(ambiguous)

    def test_accepted_first_and_day_corrections(self):
        normalized, change, ambiguous = normalize_correction('It is 7, not 6 people', {})
        self.assertEqual(normalized, 'It is 7 people')
        self.assertEqual(change, {'type': 'accepted_value', 'from': '6', 'to': '7'})
        self.assertFalse(ambiguous)
        normalized, change, ambiguous = normalize_correction(
            'Book it Tuesday, actually Wednesday and include lunch', {})
        self.assertEqual(normalized, 'Book it Wednesday and include lunch')
        self.assertEqual(change['from'], 'Tuesday')
        self.assertEqual(change['to'], 'Wednesday')
        self.assertFalse(ambiguous)

    def test_model_like_values_still_use_alias_safety(self):
        aliases = {'s1': 'LumaPad S1', 's2': 'LumaPad S2'}
        normalized, change, ambiguous = normalize_correction(
            'LumaPad S1 warranty, sorry I meant S99', aliases)
        self.assertEqual(normalized, 'LumaPad S1 warranty, sorry I meant S99')
        self.assertIsNone(change)
        self.assertTrue(ambiguous)

    def setUp(self):
        self.runtime = LiveRuntime(backend='lightweight', parser='rules')
        self.connection = self.runtime.connection()

    async def asyncTearDown(self):
        await self.connection.close()

    async def submit(self, text, number, final=True):
        return await self.connection.handle(TranscriptMessage(
            event_id=f'e{number}', turn_id='t', sequence=number,
            timestamp_ms=number*500, text=text, is_final=final))

    async def test_correction_replaces_subject_and_invalidates_old_candidates(self):
        await self.submit('LumaPad S1 warranty', 1, False)
        await self.submit('LumaPad S1 warranty period', 2, False)
        raw = 'LumaPad S1 warranty period, sorry I meant S2'
        result = await self.submit(raw, 3)
        self.assertEqual(result['citations'], ['LumaPad_S2 §Warranty.1'])
        events = {e['event_type']: e for e in result['retrieval_events']}
        self.assertIn('provisional_invalidated', events)
        self.assertEqual(events['transcript_normalized']['payload']['raw_text'], raw)
        duplicate = await self.submit(raw, 3)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(result['answer_version'], duplicate['answer_version'])

    async def test_unknown_correction_does_not_answer_previous_subject(self):
        result = await self.submit('LumaPad S1 warranty, sorry I meant S99', 1)
        self.assertEqual(result['decision'], 'wait')
        self.assertEqual(result['citations'], [])
        self.assertTrue(result['clarification'])
        self.assertEqual(result['stats']['searches'], 0)

    async def test_compound_correction_keeps_both_intents(self):
        result = await self.submit('For LumaPad S1, what is the warranty period and what receipt opens a repair, I meant S2', 1)
        self.assertEqual(set(result['citations']), {'LumaPad_S2 §Warranty.1', 'LumaPad_S2 §Repair.1'})

    def test_ordinary_actually_is_unchanged(self):
        text = 'Does LumaPad S1 actually support wireless charging?'
        self.assertEqual(normalize_correction(text, self.runtime.decomposer.aliases), (text, None, False))

    def test_multiple_subjects_require_clarification(self):
        text = 'Compare LumaPad S1 and LumaPad S2 warranty, sorry I meant S1'
        self.assertTrue(normalize_correction(text, self.runtime.decomposer.aliases)[2])

    def test_correction_uses_corpus_aliases_not_fixture_names(self):
        aliases = {'x': 'Orion X1', 'y': 'Orion X2', 'z': 'Vega X2'}
        text, change, ambiguous = normalize_correction('Orion X1 warranty, I meant X2', aliases)
        self.assertEqual(text, 'Orion X2 warranty')
        self.assertEqual(change['to'], 'Orion X2')
        self.assertFalse(ambiguous)


if __name__ == '__main__':
    unittest.main()
