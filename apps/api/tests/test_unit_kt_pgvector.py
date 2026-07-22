"""Unit tests for the pgvector KT pipeline (Phase 2) — no network, no DB."""

import asyncio

from modules.kt.services.ingestion_service import (
    _doc_context_preamble,
    chunk_by_temporal_headers,
)
from modules.kt.services.retrieval import vector_search


class TestTemporalChunker:
    def test_no_headers_single_chunk(self):
        chunks = chunk_by_temporal_headers("just a plain paragraph")
        assert len(chunks) == 1
        assert chunks[0]["content"] == "just a plain paragraph"
        assert len(chunks[0]["time"]) == 10  # YYYY-MM-DD

    def test_date_headers_split(self):
        text = "intro\n### 2024-01-15\nalpha\n### 2024-03-02\nbeta"
        chunks = chunk_by_temporal_headers(text)
        assert [c["time"] for c in chunks] == [
            chunks[0]["time"],  # intro gets "now"
            "2024-01-15",
            "2024-03-02",
        ]
        assert "alpha" in chunks[1]["content"]
        assert chunks[1]["content"].startswith("### 2024-01-15")

    def test_quarter_header_maps_to_first_month(self):
        text = "### Q2 2024\nmigration notes"
        chunks = chunk_by_temporal_headers(text)
        assert chunks[0]["time"] == "2024-04-01"

    def test_empty_sections_dropped(self):
        text = "### 2024-01-01\n\n### 2024-02-01\ncontent"
        chunks = chunk_by_temporal_headers(text)
        assert all(c["content"].strip() for c in chunks)


class TestDocPreamble:
    def test_includes_structured_knowledge(self):
        class Doc:
            problem_statement = "Legacy system is slow"
            decisions_made = [{"decision": "use Postgres"}]
            outcome = "10x faster"
            conclusion = None
            lessons_learned = ["measure first"]
            open_questions = []

        pre = _doc_context_preamble(Doc())
        assert "Legacy system is slow" in pre
        assert "10x faster" in pre
        assert "measure first" in pre
        assert "Conclusion" not in pre

    def test_empty_doc_produces_empty_preamble(self):
        class Doc:
            problem_statement = None
            decisions_made = []
            outcome = None
            conclusion = None
            lessons_learned = []
            open_questions = []

        assert _doc_context_preamble(Doc()) == ""


class TestRetrievalFailClosed:
    def test_empty_project_grants_retrieve_nothing(self):
        # Must return [] BEFORE touching the database or the embedding.
        result = asyncio.run(vector_search([0.1] * 3072, "company-x", []))
        assert result == []

    def test_empty_embedding_retrieves_nothing(self):
        result = asyncio.run(vector_search([], "company-x", ["p1"]))
        assert result == []
