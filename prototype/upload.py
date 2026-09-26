"""Bounded, in-memory corpus import. Training records are not corpus records."""
import hashlib
import json
import re
from pathlib import PurePosixPath
from citefrontier.models import CorpusChunk


def parse_upload(files):
    if not isinstance(files, list) or not 1 <= len(files) <= 25:
        raise ValueError('Choose between 1 and 25 Markdown, text, or corpus JSON files.')
    chunks = []
    for file in files:
        if not isinstance(file, dict) or not isinstance(file.get('name'), str) or not isinstance(file.get('text'), str):
            raise ValueError('Every file needs a name and UTF-8 text.')
        name = PurePosixPath(file['name'].replace('\\', '/')).name
        text = file['text'].lstrip('\ufeff').replace('\r\n', '\n')
        suffix = PurePosixPath(name).suffix.lower()
        if len(text) > 250_000:
            raise ValueError('Each document must be at most 250,000 characters.')
        digest = hashlib.sha256(text.encode()).hexdigest()
        if suffix == '.json':
            try:
                records = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError('Invalid corpus JSON.') from exc
            if not isinstance(records, list) or not records:
                raise ValueError('Corpus JSON must be an array of document chunks, not a benchmark or training dataset.')
            for record in records:
                if not isinstance(record, dict) or not all(isinstance(record.get(k), str) and record[k].strip() for k in ('doc_id','section','text')):
                    raise ValueError('Each corpus chunk needs doc_id, section, and text. ATIS/SNIPS training records are not accepted.')
                doc, section, body = record['doc_id'], record['section'], record['text']
                metadata = record.get('metadata') or {}
                if not isinstance(metadata, dict) or not all(isinstance(v, str) for v in metadata.values()):
                    raise ValueError('Chunk metadata must contain string values.')
                # Preserve declared entity names, but mark offsets in the uploaded chunk.
                chunks.append(CorpusChunk(f'{doc} §{section}',doc,section,body,
                    {'entity':metadata.get('entity',doc.replace('_',' ')), 'source':name,
                     'source_hash':digest,'start':'0','end':str(len(body)), 'offset_basis':'uploaded JSON chunk text'}))
        elif suffix in {'.md','.txt'}:
            doc = PurePosixPath(name).stem
            headings = list(re.finditer(r'(?m)^## ([^\n]+)(?:\n|$)',text))
            sections = [(m.group(1).strip(),m.end(),headings[i+1].start() if i+1<len(headings) else len(text)) for i,m in enumerate(headings)]
            if not sections:
                sections = [('Content.1',0,len(text))]
            for section, start, end in sections:
                raw = text[start:end]
                body = raw.strip()
                start += len(raw)-len(raw.lstrip())
                if body:
                    chunks.append(CorpusChunk(f'{doc} §{section}',doc,section,body,
                        {'entity':doc.replace('_',' '),'source':name,'source_hash':digest,'start':str(start),'end':str(start+len(body))}))
        else:
            raise ValueError('Supported formats: .md, .txt, and corpus .json. Convert PDF documents to sectioned text first.')
    if not chunks or len(chunks)>250:
        raise ValueError('Upload must contain between 1 and 250 nonempty sections.')
    if len({c.chunk_id for c in chunks}) != len(chunks):
        raise ValueError('Duplicate document/section IDs. Rename duplicate files or headings.')
    if any(len(c.text)>16000 or len(c.doc_id)>150 or len(c.section)>150 for c in chunks):
        raise ValueError('Use sections of at most 16,000 characters and IDs of at most 150 characters.')
    return tuple(chunks)
