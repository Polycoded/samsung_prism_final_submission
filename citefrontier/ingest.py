"""Corpus ingestion with stable, citeable LangChain-derived chunks.

LangChain is deliberately limited to `Document` normalization and splitting.
No LangChain agent, checkpoint, generic QA chain, or generated Cypher is used.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .models import CorpusChunk


class IngestionError(ValueError):
    pass


def _imports():
    try:
        from langchain_core.documents import Document
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:  # pragma: no cover - installation dependent
        raise RuntimeError("Install the ingestion extra: python -m pip install -e '.[ingestion]'") from exc
    return Document, RecursiveCharacterTextSplitter


def _as_metadata_string(value: object) -> str:
    return str(value) if value is not None else ""


def chunk_documents(
    documents: Iterable[object],
    *,
    chunk_size: int = 900,
    chunk_overlap: int = 120,
) -> tuple[CorpusChunk, ...]:
    """Convert LangChain Documents into immutable `[Doc_ID §Section]` chunks."""

    _, splitter_type = _imports()
    documents = tuple(documents)
    if not documents:
        return ()
    splitter = splitter_type(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    splits = splitter.split_documents(documents)
    ordinals: defaultdict[tuple[str, str], int] = defaultdict(int)
    chunks: list[CorpusChunk] = []
    for split in splits:
        metadata = dict(split.metadata)
        doc_id = _as_metadata_string(metadata.get("doc_id")).strip()
        if not doc_id:
            raise IngestionError("Every source Document needs immutable metadata['doc_id']")
        section = _as_metadata_string(metadata.get("section")).strip()
        if not section:
            page = _as_metadata_string(metadata.get("page")).strip()
            section = f"p.{int(page) + 1}" if page.isdigit() else "unsectioned"
        ordinal_key = (doc_id, section)
        ordinals[ordinal_key] += 1
        ordinal = ordinals[ordinal_key]
        section_id = section if ordinal == 1 else f"{section}.{ordinal}"
        source_metadata = {
            "source": _as_metadata_string(metadata.get("source")),
            "page": _as_metadata_string(metadata.get("page")),
            "start_index": _as_metadata_string(metadata.get("start_index")),
            "section": section,
        }
        chunks.append(
            CorpusChunk(
                chunk_id=f"{doc_id} §{section_id}",
                doc_id=doc_id,
                section=section_id,
                text=split.page_content.strip(),
                metadata=source_metadata,
            )
        )
    return tuple(chunks)


def load_pdf(path: Path, doc_id: str | None = None) -> tuple[CorpusChunk, ...]:
    """Load a text-extractable PDF and preserve page-level citation metadata."""

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - installation dependent
        raise RuntimeError("Install the ingestion extra: python -m pip install -e '.[ingestion]'") from exc
    document_type, _ = _imports()
    if not path.exists():
        raise FileNotFoundError(path)
    resolved_doc_id = doc_id or re.sub(r"[^A-Za-z0-9_-]+", "_", path.stem).strip("_")
    reader = PdfReader(str(path))
    pages = []
    for page_number, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(
                document_type(
                    page_content=text,
                    metadata={
                        "doc_id": resolved_doc_id,
                        "source": str(path),
                        "page": page_number,
                        "section": f"p.{page_number + 1}",
                    },
                )
            )
    if not pages:
        raise IngestionError(f"No extractable text found in {path.name}; use OCR before ingestion")
    return chunk_documents(pages)
