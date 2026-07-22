"""pgvector-backed KT chunk storage — replaces the Neo4j episode graph.

An approved KTDocument is parsed → chunked → embedded → stored here. RAG chat
retrieves by cosine distance over ``embedding``. Introduced in Phase 1
(additive); the ingestion/rag services land in Phase 2.
See docs/product-plan/TARGET_ARCHITECTURE.md §2.
"""

import datetime

from database import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# Gemini embedding dimensionality. The live-verified KT pipeline embeds at
# 3072 dims (matches the old Neo4j kt_vector_index) — keep it, do NOT assume
# 768. pgvector ANN indexes (ivfflat/hnsw) cap at 2000 dims, so retrieval is
# an exact scan for now; corpora are small (per-enterprise docs). If latency
# ever matters, switch to halfvec(3072) + HNSW.
EMBEDDING_DIM = 3072


class KTDocumentChunk(Base):
    __tablename__ = "kt_document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("kt_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized scoping keys, matching the KT idiom (KTDocument carries
    # project_id/company_id/organization_id) so retrieval filters don't need
    # a join per candidate row.
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # ISO date (YYYY-MM-DD) extracted by the temporal chunker from
    # "### 2024-03-01" / "### Q1 2024" headers — powers timeline queries.
    reference_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document = relationship("KTDocument", backref="chunks")

    __table_args__ = (
        Index("ix_kt_chunks_doc_order", "document_id", "chunk_index", unique=True),
    )
