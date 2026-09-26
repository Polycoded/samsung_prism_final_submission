import json
import unittest
from fastapi.testclient import TestClient
from prototype.server import app
from prototype.upload import parse_upload


DOCUMENT = {'name':'Orion_X1.md','text':'# Orion X1\n\n## Warranty.1\n\nOrion X1 has a 9-month limited warranty.\n'}


class UploadTests(unittest.TestCase):
    def test_markdown_provenance_and_sections(self):
        chunks = parse_upload([DOCUMENT])
        self.assertEqual(chunks[0].chunk_id, 'Orion_X1 §Warranty.1')
        self.assertEqual(chunks[0].metadata['entity'], 'Orion X1')
        start,end = int(chunks[0].metadata['start']),int(chunks[0].metadata['end'])
        self.assertEqual(DOCUMENT['text'][start:end],chunks[0].text)

    def test_training_data_and_duplicate_ids_rejected(self):
        for files in [[{'name':'train.json','text':json.dumps([{'tokens':['hello'],'labels':[0]}])}], [DOCUMENT,DOCUMENT], [{'name':'scan.pdf','text':'fake pdf'}], []]:
            with self.subTest(files=files), self.assertRaises(ValueError):
                parse_upload(files)

    def test_corpus_json_ids_are_derived_from_documents(self):
        chunks = parse_upload([{'name':'corpus.json','text':json.dumps([{'doc_id':'D','section':'S','text':'A source fact.','chunk_id':'FAKE'}])}])
        self.assertEqual(chunks[0].chunk_id,'D §S')

    def test_upload_isolated_and_invalid_upload_preserves_active_corpus(self):
        with TestClient(app) as client:
            with client.websocket_connect('/ws/stream') as first, client.websocket_connect('/ws/stream') as second:
                old = first.receive_json()
                other = second.receive_json()
                first.send_json({'type':'corpus_upload','files':[DOCUMENT]})
                uploaded = first.receive_json()
                self.assertEqual(uploaded['type'],'corpus_loaded')
                self.assertNotEqual(uploaded['session_id'],old['session_id'])
                first.send_json({'event_id':'a','turn_id':'a','text':'Orion X1 warranty period','timestamp_ms':0,'is_final':True})
                result = first.receive_json()
                self.assertEqual(result['citations'],['Orion_X1 §Warranty.1'])
                second.send_json({'event_id':'a','turn_id':'a','text':'LumaPad S1 warranty period','timestamp_ms':0,'is_final':True})
                self.assertEqual(second.receive_json()['citations'],['LumaPad_S1 §Warranty.1'])
                first.send_json({'type':'corpus_upload','files':[]})
                self.assertEqual(first.receive_json()['type'],'error')
                path=f"/session/{uploaded['session_id']}/corpus"
                self.assertEqual(client.get(path).status_code,403)
                auth={'Authorization':f"Bearer {uploaded['session_token']}"}
                self.assertEqual(client.get(path,headers=auth).json()[0]['doc_id'],'Orion_X1')
                self.assertEqual(client.get(f"/session/{old['session_id']}/corpus").status_code,404)
                self.assertEqual(len(client.get('/corpus').json()),30)
            self.assertEqual(client.get(path,headers=auth).status_code,404)


if __name__ == '__main__':
    unittest.main()
