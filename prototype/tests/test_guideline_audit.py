import unittest
from unittest.mock import patch
from prototype.runtime import LiveRuntime
from prototype.server import TranscriptMessage, demo_scenarios


class GuidelineAuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_formatting_prefixes_do_not_retrieve(self):
        runtime = LiveRuntime(backend='lightweight', parser='rules')
        for text in ['Please repeat your last answer in two bullets.', 'Make that shorter',
                     'Put that in bullets', 'Translate your last answer into French']:
            with self.subTest(text=text):
                connection = runtime.connection()
                try:
                    initial = await connection.handle(TranscriptMessage(event_id='base',turn_id='base',text='LumaPad S1 warranty period',timestamp_ms=0,is_final=True))
                    before = connection.search_count
                    tokens = text.split()
                    for n in range(1,len(tokens)+1):
                        result = await connection.handle(TranscriptMessage(event_id=f'e{n}',turn_id='format',text=' '.join(tokens[:n]),timestamp_ms=n*200,is_final=n==len(tokens)))
                    self.assertEqual(connection.search_count, before)
                    self.assertEqual(result['decision'], 'suppress')
                    self.assertEqual(result['claims'], initial['claims'])
                    if text.startswith('Translate'):
                        self.assertIn('not supported',result['clarification'])
                finally:
                    await connection.close()

    def test_demo_fixtures_can_be_disabled(self):
        with patch.dict('os.environ', {'CITEFRONTIER_DEMO':'0'}):
            self.assertEqual(demo_scenarios(), {})

    async def test_requested_bullet_count_preserves_all_claims_and_citations(self):
        runtime=LiveRuntime(backend='lightweight',parser='rules')
        connection=runtime.connection()
        try:
            initial=await connection.handle(TranscriptMessage(event_id='i',turn_id='i',text='For LumaPad S1, what is the warranty period and what liquid damage is excluded and what receipt opens a repair?',timestamp_ms=0,is_final=True))
            result=await connection.handle(TranscriptMessage(event_id='f',turn_id='f',text='Repeat your last answer in two bullets',timestamp_ms=1000,is_final=True))
            self.assertEqual(len(result['presentation_items']),2)
            self.assertEqual(result['claims'],initial['claims'])
            self.assertEqual(result['stats'],initial['stats'])
            self.assertEqual([c for item in result['presentation_items'] for c in item['citations']],initial['citations'])
        finally:
            await connection.close()


if __name__ == '__main__':
    unittest.main()
