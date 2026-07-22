"""Unit tests for KT pipeline pure logic (no network): chunking, citations, context."""
from services.kt_langraph import _build_context, _extract_citations
from services.kt_workflows import KTIngestionService, _sprint_label


def test_sprint_label_quarter_bucketing():
    assert _sprint_label("2024-01-10") == "Q1 2024"
    assert _sprint_label("2024-05-20") == "Q2 2024"
    assert _sprint_label("2023-11-02") == "Q4 2023"
    assert _sprint_label("garbage") == "Undated"


def test_chunk_by_temporal_headers_splits_on_dates():
    text = (
        "### 2024-04-15\nWe shipped the billing service.\n"
        "### 2024-05-20\nWe added webhook verification."
    )
    chunks = KTIngestionService.chunk_by_temporal_headers(text)
    assert len(chunks) == 2
    assert chunks[0]["time"] == "2024-04-15"
    assert chunks[1]["time"] == "2024-05-20"
    assert "billing" in chunks[0]["content"]


def test_chunk_by_temporal_headers_quarter_header():
    chunks = KTIngestionService.chunk_by_temporal_headers("### Q3 2024\nSome retro notes.")
    assert chunks[0]["time"] == "2024-07-01"  # Q3 -> month 7


def test_chunk_no_headers_single_chunk():
    chunks = KTIngestionService.chunk_by_temporal_headers("Just a plain body with no headers.")
    assert len(chunks) == 1
    assert chunks[0]["content"] == "Just a plain body with no headers."


def test_extract_citations_maps_titles_to_sources():
    chunks = [
        {"doc_id": "d1", "doc_title": "Payment Retry Design", "content": "backoff", "project_name": "P"},
        {"doc_id": "d2", "doc_title": "Webhook Guide", "content": "verify", "project_name": "P"},
    ]
    resp = "Use backoff [citation: Payment Retry Design] and verify [citation: Webhook Guide]."
    sources = _extract_citations(resp, chunks)
    ids = {s["doc_id"] for s in sources}
    assert ids == {"d1", "d2"}


def test_extract_citations_dedupes_and_ignores_unknown():
    chunks = [{"doc_id": "d1", "doc_title": "Doc A", "content": "x", "project_name": "P"}]
    resp = "[citation: Doc A] ... again [citation: Doc A] ... [citation: Nonexistent]"
    sources = _extract_citations(resp, chunks)
    assert len(sources) == 1 and sources[0]["doc_id"] == "d1"


def test_build_context_numbers_and_titles_sources():
    chunks = [{"doc_id": "d1", "doc_title": "Runbook", "content": "step one"}]
    ctx = _build_context(chunks)
    assert "[Source 1 — Runbook]" in ctx
    assert "step one" in ctx
