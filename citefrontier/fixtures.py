"""Disclosed synthetic fixture corpus and replay traces for validation only."""

from __future__ import annotations

from .models import CorpusChunk, TranscriptEvent
from .retrieval import HybridRetriever, InMemoryCorpusGraph


def fixture_retriever() -> HybridRetriever:
    chunks = (
        CorpusChunk(
            "Doc_Venue §1",
            "Doc_Venue",
            "1",
            "Pune Venue A supports customer workshops with a capacity of 30 attendees.",
        ),
        CorpusChunk(
            "Doc_Cancellation §2",
            "Doc_Cancellation",
            "2",
            "Workshop cancellation terms allow changes until seven days before the event.",
        ),
        CorpusChunk(
            "Doc_Catering §1",
            "Doc_Catering",
            "1",
            "Catering options include on-site lunch and external vegetarian catering.",
        ),
        CorpusChunk(
            "Doc_Travel §1",
            "Doc_Travel",
            "1",
            "Employee travel reimbursement requires an approved business trip and itemized receipts.",
        ),
        CorpusChunk(
            "Doc_Travel §4",
            "Doc_Travel",
            "4",
            "International trips with bookings made after travel require senior director approval and foreign currency receipt verification.",
        ),
        CorpusChunk(
            "Doc_Warranty_A §1",
            "Doc_Warranty_A",
            "1",
            "Model A device warranty lasts one year from the date of purchase.",
        ),
        CorpusChunk(
            "Doc_Warranty_B §1",
            "Doc_Warranty_B",
            "1",
            "Model B device warranty lasts two years from the date of purchase.",
        ),
    )
    graph = InMemoryCorpusGraph(
        {
            "Doc_Travel §1": ("Doc_Travel §4",),
            "Doc_Venue §1": ("Doc_Cancellation §2", "Doc_Catering §1"),
        }
    )
    return HybridRetriever(chunks, graph)


def multi_intent_trace() -> tuple[TranscriptEvent, ...]:
    return (
        TranscriptEvent(0.0, "I need to plan a customer workshop in"),
        TranscriptEvent(0.8, "I need to plan a customer workshop in Pune for 30 people and I need"),
        TranscriptEvent(
            1.6,
            "I need to plan a customer workshop in Pune for 30 people and I need the cancellation policy and catering options",
        ),
        TranscriptEvent(
            2.1,
            "I need to plan a customer workshop in Pune for 30 people and I need the cancellation policy and catering options",
            is_final=True,
        ),
    )
