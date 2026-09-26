from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from langchain_core.documents import Document
from pypdf import PdfWriter

from citefrontier.ingest import IngestionError, chunk_documents, load_pdf


class IngestionTests(unittest.TestCase):
    def test_chunks_have_stable_doc_section_citations_and_offsets(self) -> None:
        document = Document(
            page_content="Warranty terms apply to purchased devices. " * 80,
            metadata={"doc_id": "Doc_Warranty", "source": "fixture.pdf", "page": 0, "section": "Warranty"},
        )
        chunks = chunk_documents((document,), chunk_size=180, chunk_overlap=20)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_id, "Doc_Warranty §Warranty")
        self.assertEqual(chunks[1].chunk_id, "Doc_Warranty §Warranty.2")
        self.assertEqual(chunks[0].metadata["page"], "0")
        self.assertTrue(chunks[0].metadata["start_index"].isdigit())

    def test_missing_doc_id_is_rejected(self) -> None:
        document = Document(page_content="A source without provenance", metadata={"page": 0})
        with self.assertRaises(IngestionError):
            chunk_documents((document,))

    def test_textless_pdf_requires_ocr_instead_of_silent_empty_ingestion(self) -> None:
        with TemporaryDirectory() as temp_directory:
            source = Path(temp_directory) / "scan.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            with source.open("wb") as handle:
                writer.write(handle)
            with self.assertRaisesRegex(IngestionError, "No extractable text"):
                load_pdf(source, "Doc_Scan")


if __name__ == "__main__":
    unittest.main()
