# StudyHubV2 Target Architecture & Migration Plan

**Status:** FINAL ARCHITECTURE DESIGN  
**Date:** 2026-07-22  
**Scope:** Single-enterprise quiz + KT platform restructure (FastAPI + Next.js 15)  
**Product:** Quiz/Assessment + Knowledge Transfer (KT) as distinct products sharing platform core

---

## EXECUTIVE SUMMARY

StudyHubV2 is a 35.5K-line backend + 28.3K-line frontend monolith with a broken KT ingestion pipeline and severely fragmented frontend routing. This plan restructures it into a clean, maintainable modular monolith (backend) + proper App Router SPA (frontend) while keeping the system running through phased incremental migration.

**Key Wins:**
- Kill 12 god files (kt.py: 3,893→~600 lines, LDAdminDashboard: 2,977→<500 each)
- Replace failed Neo4j pipeline with pgvector-based RAG on proven Postgres/asyncpg
- Full URL routing for the frontend (no more state-machine SPA)
- Clear module boundaries (identity, org, assessment, kt, reporting) with services layer
- Single async DB session pattern throughout
- Typed API client with React Query everywhere

**Timeline:** 8 phases, ~12-16 weeks, parallel streams possible from Phase 3 onward

---

## 1. BACKEND TARGET STRUCTURE: MODULAR MONOLITH

### 1.1 Module Layout

```
apps/api/
├── main.py                             # FastAPI app init, CORS, middleware, error handlers
├── config.py                           # Pydantic Settings (env-driven)
├── database.py                         # SQLAlchemy: async session, engine, Base
├── auth_utils.py                       # JWT decode, org scoping, role checks (simplified)
├── error_handlers.py                   # Custom exceptions, error middleware
│
├── modules/
│   ├── __init__.py
│   │
│   ├── platform/                       # Platform Operator (vendor side)
│   │   ├── __init__.py
│   │   ├── models.py                   # No new entities; reuses SuperOrganization
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── super_org.py            # (from platform.py: 1 router, ~80 ep → ~20 ep)
│   │   ├── services/
│   │   │   └── super_org_service.py    # Tenant lifecycle, billing query stubs
│   │   └── schemas.py
│   │
│   ├── identity/                       # Auth, users, roles (enterprise-agnostic)
│   │   ├── __init__.py
│   │   ├── models.py                   # User, UserRole, Group, etc.
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                 # (from auth.py: 2,381 lines → ~1,100: login, register, refresh, logout, password reset)
│   │   │   ├── profile.py              # (from profile.py: ~150 lines: user profile CRUD, badges)
│   │   │   └── roles.py                # (NEW: role assignment, enterprise role CRUD)
│   │   ├── services/
│   │   │   ├── auth_service.py         # Hashing, JWT generation, token validation
│   │   │   ├── user_service.py         # User CRUD, role assignment, skill tagging
│   │   │   └── email_service.py        # (from services; send invites, password resets)
│   │   └── schemas.py
│   │
│   ├── org/                            # Organization hierarchy (Org → Dept → Vertical → Batch → Group)
│   │   ├── __init__.py
│   │   ├── models.py                   # OrgUnit (consolidated: type enum), UserRole on OrgUnit, Group
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── hierarchy.py            # (from admin.py + org.py: CRUD Org/Dept/Vertical/Batch/Group)
│   │   │   ├── units.py                # (from admin.py + org.py: OrgUnit API if kept modular)
│   │   │   └── users.py                # (from admin.py: user assignment to OrgUnits)
│   │   ├── services/
│   │   │   ├── hierarchy_service.py    # Tree CRUD, ancestor/descendant queries
│   │   │   ├── role_scope_service.py   # Permission scoping: which OrgUnits can a user access?
│   │   │   └── group_service.py        # Group membership, batch assignments
│   │   └── schemas.py
│   │
│   ├── assessment/                     # Quiz, Exam, Gradebook, Coding
│   │   ├── __init__.py
│   │   ├── models.py                   # Question, QuestionBank, Exam, Attempt, CodingQuestion, etc.
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── quiz.py                 # (from quiz.py: 2,119 lines → ~800: bank CRUD, exam flows)
│   │   │   ├── exam.py                 # (from exam.py: ~300 lines: exam attempt lifecycle)
│   │   │   ├── coding.py               # (from code.py: ~300 lines: coding challenge CRUD + test execution)
│   │   │   ├── gradebook.py            # (from gradebook.py: ~100 lines: attempt grades summary)
│   │   │   └── assignment.py           # (from assignment.py: ~350 lines: exam assignment to groups)
│   │   ├── services/
│   │   │   ├── quiz_service.py         # Question bank ops, exam orchestration
│   │   │   ├── exam_service.py         # Attempt startup, question delivery, answer submission
│   │   │   ├── grading_service.py      # (from services/grading.py: scoring logic)
│   │   │   ├── coding_service.py       # Code execution, test case evaluation
│   │   │   └── assignment_service.py   # Assignment CRUD, batch assignment
│   │   └── schemas.py
│   │
│   ├── kt/                             # Knowledge Transfer (document management + RAG)
│   │   ├── __init__.py
│   │   ├── models.py                   # KTProject, KTDocument, KTAccessKey, KTChatSession, etc.
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── documents.py            # (from kt.py: ~800 lines: doc CRUD, versioning, submit → review)
│   │   │   ├── review.py               # (from kt.py: ~400 lines: reviewer workflow, approval)
│   │   │   ├── ingestion.py            # (from kt.py + services/job_handlers: ~300 lines: status polling, job enqueue)
│   │   │   ├── chat.py                 # (from kt.py: ~500 lines: RAG chat, session management)
│   │   │   ├── handoff.py              # (from kt.py: ~300 lines: exit handoff initiation/completion)
│   │   │   ├── access.py               # (from kt.py: ~200 lines: access key generation/validation)
│   │   │   └── projects.py             # (from kt.py: ~400 lines: KTProject CRUD, membership)
│   │   ├── services/
│   │   │   ├── document_service.py     # Document lifecycle: draft → submitted → approved
│   │   │   ├── ingestion_service.py    # (from services/kt_engine.py + kt_workflows.py: chunking, embedding, pgvector)
│   │   │   ├── rag_service.py          # (from services/kt_langraph.py: chat logic over pgvector)
│   │   │   ├── access_service.py       # Access key generation, signing, validation
│   │   │   └── notification_service.py # Document status notifications
│   │   └── schemas.py
│   │
│   ├── ai/                             # AI/ML infrastructure (embeddings, LLM orchestration)
│   │   ├── __init__.py
│   │   ├── models.py                   # AIUsage, AICache (for cost metering)
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── ai.py                   # (from ai.py: 1,119 lines → ~400: query GPT/Gemini, content generation for quiz)
│   │   │   ├── meter.py                # (from ai_meter.py: AI usage tracking)
│   │   │   └── cache.py                # (from ai_cache via models: cache hit/miss analytics)
│   │   ├── services/
│   │   │   ├── embedding_service.py    # (from services/ai_engine.py + vector_service.py: pgvector embeddings)
│   │   │   ├── llm_service.py          # LLM calls (Gemini, GPT wrappers, rate limiting)
│   │   │   ├── cache_service.py        # Redis caching for embeddings
│   │   │   └── meter_service.py        # Token/cost tracking
│   │   └── schemas.py
│   │
│   ├── reporting/                      # Analytics, reports, performance dashboards
│   │   ├── __init__.py
│   │   ├── models.py                   # No new entities; joins on assessment/kt/identity tables
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── quiz_reports.py         # (from reports.py: ~1,000 lines → ~600: leaderboard, attempt analytics, exports)
│   │   │   ├── kt_reports.py           # (NEW: KT doc ingestion status, chat analytics, handoff tracking)
│   │   │   ├── performance.py          # (from intel.py + performance_engine.py: ~400 lines: skills/learning curves)
│   │   │   └── audit.py                # (from audit_service.py: compliance, action logs)
│   │   ├── services/
│   │   │   ├── quiz_analytics.py       # (from services/analytics.py + performance_engine.py: attempt stats)
│   │   │   ├── kt_analytics.py         # KT document metrics
│   │   │   ├── performance_service.py  # (from services/performance_engine.py: skill curves, recommendations)
│   │   │   └── audit_service.py        # Audit log recording
│   │   └── schemas.py
│   │
│   └── jobs/                           # Background jobs (async work, scheduling)
│       ├── __init__.py
│       ├── models.py                   # BackgroundJob, JobStatus (already exists)
│       ├── handlers.py                 # (from services/job_handlers.py: JOB_KT_INGEST, JOB_EMAIL, etc.)
│       └── queue.py                    # (from services/job_queue.py: enqueue, dequeue, Postgres-backed durable queue)
│
├── shared/                              # Cross-cutting utilities
│   ├── __init__.py
│   ├── exceptions.py                   # AuthError, OrgScopeError, ValidationError, etc.
│   ├── middleware.py                   # CORS, request ID logging, org scoping
│   ├── permissions.py                  # @require_role, @require_org_access decorators
│   ├── validators.py                   # Reusable Pydantic validators
│   └── constants.py                    # Enums, magic strings (moved from scattered places)
│
├── migrations/                          # Alembic
│   ├── versions/                       # (existing: use these as-is during migration)
│   ├── env.py
│   └── alembic.ini
│
└── tests/
    ├── conftest.py                     # pytest fixtures
    ├── test_auth.py                    # Identity tests
    ├── test_org.py                     # Hierarchy tests
    ├── test_assessment.py              # Quiz/exam tests
    ├── test_kt.py                      # KT workflow tests
    └── ...
```

### 1.2 Router Splitting Strategy (God File Refactor)

#### **kt.py (3,893 lines → 8 routers, ~600 lines each)**
Current monolith mixes:
- Document CRUD (draft, submit, version)
- Review workflow (approve, reject, comments)
- Ingestion pipeline (chunk, embed, feed to Neo4j) — **BROKEN, will replace**
- RAG chat (session, message, feedback)
- Access key management (generate, validate, sign)
- Project membership
- Handoff workflow
- Audit logging

**Split to:**
- `modules/kt/routers/documents.py` — CRUD, versioning, status transitions (draft→submitted)
- `modules/kt/routers/review.py` — Reviewer workflow (under_review→approved/rejected)
- `modules/kt/routers/ingestion.py` — Job queue trigger, status polling (replaces broken Neo4j pipeline)
- `modules/kt/routers/chat.py` — RAG chat (session, messages, feedback)
- `modules/kt/routers/access.py` — API key lifecycle
- `modules/kt/routers/projects.py` — Project CRUD, membership
- `modules/kt/routers/handoff.py` — Exit handoff initiation/completion
- `modules/kt/routers/audit.py` — Audit log queries (audit_service)

**Service layer:**
- `services/kt_engine.py` (815 lines) → delete most; keep helper functions in `ingestion_service.py`
- `services/kt_langraph.py` (12K, LLM RAG with Neo4j) → **REPLACE** with `rag_service.py` (pgvector-based)
- `services/kt_workflows.py` (15K) → consolidate into `ingestion_service.py` + `document_service.py`

#### **auth.py (2,381 lines → 2 routers, ~1,100 + ~200 lines)**
Splits cleanly:
- `modules/identity/routers/auth.py` — Login, register, refresh, logout, password reset, 2FA (when added)
- `modules/identity/routers/roles.py` — Role CRUD, assignment (new, currently in admin.py)
- `modules/identity/routers/profile.py` — already separated in profile.py, move as-is

#### **quiz.py (2,119 lines → 2 routers, ~1,000 + ~800 lines)**
- `modules/assessment/routers/quiz.py` — Bank CRUD, exam creation, question CRUD
- `modules/assessment/routers/exam.py` — Exam attempt delivery, answer submission, completion

#### **admin.py (814 lines → 3 routers)**
Currently: org hierarchy CRUD + user assignment + audit queries
- `modules/org/routers/hierarchy.py` — Org/Dept/Vertical/Batch CRUD
- `modules/org/routers/users.py` — User assignment to groups, role scoping
- `modules/reporting/routers/audit.py` — Audit log queries (moves to reporting module)

#### **reports.py (1,861 lines → 2 routers)**
- `modules/reporting/routers/quiz_reports.py` — Leaderboard, attempt stats, export
- `modules/reporting/routers/performance.py` — Skills graph, learning curves (split from intel.py)

#### **ai.py (1,119 lines → 2 routers, ~500 + ~200 lines)**
- `modules/ai/routers/ai.py` — LLM call APIs (content generation, prompt testing)
- `modules/ai/routers/meter.py` — Usage metrics, cost breakdown

#### **Others remain mostly as-is:**
- exam.py → `modules/assessment/routers/exam.py` (already <400 lines, well-scoped)
- code.py → `modules/assessment/routers/coding.py` (already <300 lines)
- mentor.py (1,017 lines) → keep as `modules/assessment/routers/mentor.py` for now; refactor in Phase 5
- assignment.py → `modules/assessment/routers/assignment.py`
- interaction.py → could merge into `modules/assessment/routers/discussion.py` or stay separate
- resources.py → `modules/platform/routers/resources.py` (not yet categorized; learning materials?)
- contact.py → `modules/platform/routers/contact.py` (small, stays)

### 1.3 Service Layer Pattern

**Rule:** Every router depends ONLY on services (not on models directly for complex ops).

**Service Signature Template:**
```python
# modules/assessment/services/quiz_service.py
class QuizService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_bank(self, org_id: int, data: BankCreateRequest) -> QuestionBank:
        """Create a question bank in org context."""
        # Query, validate org_id, insert, return

    async def list_banks(self, org_id: int) -> List[QuestionBank]:
        """List banks accessible by org."""
        # Query with org_id filter

    async def get_bank_with_questions(self, org_id: int, bank_id: int) -> BankWithQuestions:
        """Load bank + questions (prevents N+1)."""
        # Eager-load relationships
```

**Dependency Injection in Routers:**
```python
# modules/assessment/routers/quiz.py
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/quiz", tags=["quiz"])

async def get_quiz_service(db: AsyncSession = Depends(get_db)) -> QuizService:
    return QuizService(db)

@router.post("/banks")
async def create_bank(
    org_id: int = Depends(get_org_from_token),
    data: BankCreateRequest,
    service: QuizService = Depends(get_quiz_service),
):
    return await service.create_bank(org_id, data)
```

### 1.4 Database Session Pattern: Single Async Standard

**Current state:** Mixed async/sync; some endpoints use `get_db()` (sync), some `Depends(get_async_db)` (async).

**Target:** 100% async, single pattern everywhere.

```python
# database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    poolclass=NullPool,  # Heroku/serverless
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncSession:
    """Dependency: async session per request."""
    async with SessionLocal() as session:
        yield session
```

**Migration plan:**
1. Phase 1: Keep both sync + async working (backward compat)
2. Phase 2-3: Convert routers incrementally to async-only
3. Phase 4: Remove sync session factory entirely

---

## 2. KT RE-ARCHITECTURE: PGVECTOR-BASED RAG

### 2.1 Problem Statement (Current Broken Pipeline)

```
User uploads KT Document (PDF/Markdown)
    ↓ (submit_document endpoint)
KTDocument status = "submitted"
    ↓ (background job: JOB_KT_INGEST)
Chunking → Embedding (Gemini) → Neo4j Ingestion
    ↓ ❌ FAILS: Neo4j driver errors, empty graph
KTDocument status stays "submitted" (never reaches "ingested")
    ↓ (user wants to chat)
KT Chat endpoint tries Neo4j query → returns empty results
    ↓ User sees useless chatbot with zero knowledge
```

**Root causes:**
1. Neo4j not initialized, no driver configured properly
2. Gemini embedding pipeline has sync/async mismatch
3. kt_langraph.py uses deprecated LangChain/LangGraph APIs
4. No retry logic, job failure is silent

### 2.2 Target Pipeline (Postgres + pgvector)

```
User uploads KT Document
    ↓
KTDocument status = "draft"
    ↓
User submits (endpoint: POST /api/kt/documents/{doc_id}/submit)
    ↓
KTDocument status = "submitted"
  + enqueue job: JOB_KT_INGEST (BackgroundJob.type = "kt_ingest")
    ↓ (async background worker)
KT Ingestion Job Handler:
  1. Fetch document + attachments from S3
  2. Parse (PDF/MD/TXT)
  3. Chunk (by section, ~512 tokens overlap ~100 tokens)
  4. Embed each chunk (Gemini API, cached in Redis)
  5. Insert chunks + embeddings into Postgres (pgvector)
  6. Update KTDocument status = "approved" (approval auto-granted for now; later: reviewer workflow)
  7. Update ingestion_job status = "complete"
    ↓
User queries chat
    ↓
Chat handler (POST /api/kt/chat/message):
  1. Query pgvector (cosine similarity, top-k=5)
  2. Format results into RAG prompt
  3. Call Gemini with prompt
  4. Stream response via Server-Sent Events
  5. Log interaction (KTChatMessage)
```

### 2.3 New Schema: pgvector Chunks Table

```python
# modules/kt/models.py - ADD NEW TABLE

class KTDocumentChunk(Base):
    """Parsed + embedded chunk of a KT document."""
    
    __tablename__ = "kt_document_chunks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("kt_documents.id", ondelete="CASCADE"), 
        index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)  # order in doc
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    # pgvector column: 768-dim (Gemini embedding)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    tokens: Mapped[int] = mapped_column(Integer)  # for cost tracking
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    # Relationship
    document = relationship("KTDocument", back_populates="chunks")
    
    __table_args__ = (
        Index("ix_kt_chunks_embedding", "embedding", postgresql_using="ivfflat"),
    )
```

### 2.4 Service Layer: Ingestion + RAG

**File:** `modules/kt/services/ingestion_service.py`

```python
class KTIngestionService:
    """Handle document → chunks → pgvector pipeline."""
    
    async def ingest_document(
        self, 
        doc_id: int, 
        db: AsyncSession
    ) -> IngestResult:
        """Main pipeline: fetch → parse → chunk → embed → store."""
        doc = await db.get(KTDocument, doc_id)
        
        # 1. Fetch from S3
        content = await s3_service.get_object(doc.s3_key)
        
        # 2. Parse (markdown/pdf/txt)
        parsed = self._parse_content(content, doc.file_type)
        
        # 3. Chunk
        chunks = self._chunk_text(parsed, chunk_size=512, overlap=100)
        
        # 4. Embed (batch Gemini calls)
        embeddings = await embedding_service.embed_batch(chunks)
        
        # 5. Store in pgvector
        for chunk_text, embedding in zip(chunks, embeddings):
            chunk = KTDocumentChunk(
                document_id=doc_id,
                text=chunk_text,
                embedding=embedding,
                tokens=len(chunk.split()),
            )
            db.add(chunk)
        
        await db.commit()
        doc.status = "approved"  # auto-approve for now
        await db.commit()
        
        return IngestResult(chunks_count=len(chunks), total_tokens=sum(...))
    
    def _parse_content(self, content: bytes, file_type: str) -> str:
        """Markdown/PDF/TXT → text."""
        if file_type == "pdf":
            return parse_pdf(content)
        elif file_type == "markdown":
            return content.decode("utf-8")
        ...
    
    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Chunk by paragraphs/sentences respecting size."""
        # Naive: split by "\n\n", recombine to chunk_size
        # Better: use tiktoken to estimate tokens
        ...
```

**File:** `modules/kt/services/rag_service.py`

```python
class KTRAGService:
    """RAG chat over pgvector."""
    
    async def query_documents(
        self,
        query: str,
        org_id: int,
        k: int = 5,
        db: AsyncSession = None,
    ) -> List[ChunkWithScore]:
        """Find top-k similar chunks using pgvector."""
        # 1. Embed query
        query_embedding = await embedding_service.embed_text(query)
        
        # 2. Query pgvector
        stmt = select(KTDocumentChunk).where(
            KTDocumentChunk.document_id.in_(
                select(KTDocument.id).where(
                    KTDocument.company_id == org_id  # org scoping
                )
            )
        ).order_by(
            KTDocumentChunk.embedding.cosine_distance(query_embedding)
        ).limit(k)
        
        chunks = await db.scalars(stmt)
        return chunks
    
    async def chat_stream(
        self,
        session_id: str,
        user_query: str,
        org_id: int,
        db: AsyncSession,
    ):
        """Chat endpoint with streaming."""
        # 1. Retrieve session
        session = await db.get(KTChatSession, session_id)
        
        # 2. RAG retrieve
        chunks = await self.query_documents(user_query, org_id, db=db)
        
        # 3. Format prompt
        context = "\n---\n".join(c.text for c in chunks)
        prompt = f"""
        You are a knowledge assistant. Use the following context to answer:
        
        {context}
        
        User question: {user_query}
        """
        
        # 4. Stream Gemini
        async for token in llm_service.stream_gemini(prompt):
            yield f"data: {json.dumps({'token': token})}\n\n"
        
        # 5. Log interaction
        msg = KTChatMessage(
            session_id=session_id,
            role="assistant",
            content=full_response,  # accumulated from stream
        )
        db.add(msg)
        await db.commit()
```

### 2.5 Migration Path: Neo4j → pgvector

**Timeline:** Phase 2 (concurrent with first router splits)

**Steps:**
1. Deploy pgvector extension to Postgres (already available)
2. Create `KTDocumentChunk` table (migration)
3. Deploy new `ingestion_service.py` + `rag_service.py`
4. New documents → pgvector pipeline only
5. **No bulk migration of old docs** (Neo4j was empty anyway)
6. Old `KTIngestionJob` entries mark status = "legacy_failed" (audit trail)
7. Leave Neo4j untouched (don't drop, just stop querying)
8. Phase 7: Decommission Neo4j driver, clean up kt_engine.py + kt_langraph.py + kt_workflows.py

**Testing:**
- Unit test `_chunk_text()` on various formats
- Integration test `ingest_document()` with mock S3 + Gemini
- E2E test: upload doc → check chunks in pgvector → query chat → get response

---

## 3. DATA MODEL TARGET

### 3.1 Org Hierarchy Consolidation

**Current state:** 5 separate tables (Organization, Department, Vertical, Batch, Group) with hardcoded parent-child relationships.

**Target:** Single `OrgUnit` table with hierarchical tree structure (common pattern in enterprise SaaS).

**Rationale:**
- Single-enterprise means no tenant isolation needed (simplify)
- Org hierarchy is flexible (future: variable nesting levels)
- Easier permission scoping queries (one recursive CTE, not 5 tables)
- Reduces migration burden

**Schema:**
```python
# modules/org/models.py

class OrgUnitType(str, Enum):
    ORGANIZATION = "organization"
    DEPARTMENT = "department"
    VERTICAL = "vertical"
    BATCH = "batch"
    GROUP = "group"

class OrgUnit(Base):
    """Hierarchical org structure: single node in tree."""
    
    __tablename__ = "org_units"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True  # Top-level org scoping
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("org_units.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    
    unit_type: Mapped[OrgUnitType] = mapped_column(
        SAEnum(OrgUnitType),
        default=OrgUnitType.GROUP
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # For tree traversal
    path: Mapped[str] = mapped_column(String(1000))  # ltree extension OR JSON path
    depth: Mapped[int] = mapped_column(Integer, default=0)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="org_units")
    parent = relationship("OrgUnit", remote_side=[id], backref="children")
    members = relationship("UserOrgRole", back_populates="org_unit", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_org_unit_parent_name"),
        Index("ix_org_units_organization_id", "organization_id"),
    )
```

**NEW:** `UserOrgRole` (replace current org-scoped `UserRole`):
```python
class UserOrgRole(Base):
    """User + Role + OrgUnit (replaces many-to-many on 5 tables)."""
    
    __tablename__ = "user_org_roles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    org_unit_id: Mapped[int] = mapped_column(ForeignKey("org_units.id", ondelete="CASCADE"))
    
    role: Mapped[str] = mapped_column(
        String(50),
        # values: "learner", "mentor", "group_admin", "ld_admin"
    )
    
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    assigned_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    org_unit = relationship("OrgUnit", back_populates="members")
    
    __table_args__ = (
        UniqueConstraint("user_id", "org_unit_id", name="uq_user_org_unit"),
    )
```

### 3.2 Entity Consolidation Map

| Current Entity | Target | Notes |
|---|---|---|
| `SuperOrganization` | Keep as-is | Tenant billing unit |
| `Organization` | `Organization` (keep) + `OrgUnit(type=ORGANIZATION)` | Org is root of tree |
| `Department` | Migrate to `OrgUnit(type=DEPARTMENT)` | Keep data in migration |
| `Vertical` | Migrate to `OrgUnit(type=VERTICAL)` | Keep data in migration |
| `Batch` | Migrate to `OrgUnit(type=BATCH)` | Keep data in migration |
| `Group` | Migrate to `OrgUnit(type=GROUP)` | Keep data in migration |
| `User` | Keep as-is | Global identity |
| `UserRole` (current) | Migrate to `UserOrgRole` | Add org_unit_id scoping |
| `KTCompany` | **DELETE** (redundant, use org_id) | Map to Organization |
| `KTProject` | Keep; add `org_id` | Project under org tree |
| All KT entities | Keep; add `org_id` foreign key | Org-scoped KT |

### 3.3 What Gets Deleted

```python
# Delete these models entirely (no data kept):
- models/org.py → delete Department, Vertical, Batch (replace with OrgUnit)
- models/kt_model.py → delete KTCompany, KTProjectMember (simplify with org_id)
  
# Delete these files entirely:
- apps/api/fix_kt.py
- apps/api/auto_fix_pyright_2.py
- apps/api/check_users.py
- apps/api/tempgugughiu.txt
- apps/api/temppythonpullneo4j.py
- apps/api/tempFileContent.txt
- apps/api/root/*.zip, *.txt (root clutter)

# Deprecate (leave in codebase but don't use):
- services/kt_engine.py (mostly)
- services/kt_langraph.py
- services/kt_workflows.py
```

### 3.4 Migration Path: OrgUnit Introduction

**Timeline:** Phase 1 (parallel to router splits)

**Approach:** Backward-compatible. Keep old tables, introduce new ones.

**Steps:**
1. Add `KTDocumentChunk`, `OrgUnit`, `UserOrgRole` tables (Alembic)
2. Deploy code that reads BOTH old + new tables (compatibility layer)
3. Backfill script: `Department` → `OrgUnit(type=DEPARTMENT)` (one-time, Phase 1)
4. New assignments → `UserOrgRole` only; old `UserRole` stays read-only
5. Phase 5: Flip all queries to `OrgUnit` only
6. Phase 6: Archive old tables (no delete, just don't use)
7. Phase 7: Remove old tables in cleanup migration

**Compatibility Layer Example:**
```python
# shared/compatibility.py
async def get_org_units_for_user(user_id: int, db: AsyncSession):
    """Return org_units from NEW table, OR fall back to reconstructed from old tables."""
    new_results = await db.execute(
        select(UserOrgRole).filter_by(user_id=user_id)
    )
    if new_results:
        return new_results
    
    # Fallback: query old UserRole, Group, etc. and synthesize
    old_role = await db.get(UserRole, user_id)
    if old_role.group_id:
        group = await db.get(Group, old_role.group_id)
        # Reconstruct UserOrgRole on the fly
        ...
```

---

## 4. FRONTEND TARGET STRUCTURE: REAL ROUTING + DECOMPOSED COMPONENTS

### 4.1 URL Routing Map

**Current state:** 1 giant SPA (`page.tsx` 506 lines with state machine) + 10 actual Next.js routes (with deep-linking broken).

**Target:** App Router with real routes, one component per view.

```
/                              (LoginPage or Dashboard based on auth)
├── /dashboard                 (Learner dashboard: my exams, progress)
├── /exam
│   └── /[id]                  (Take exam: questions, timer, submit)
├── /exam/result/[attemptId]   (Result view: score, review answers)
│
├── /admin
│   ├── /dashboard             (L&D Admin: org overview)
│   ├── /hierarchy             (Org tree CRUD)
│   ├── /users                 (User management, bulk import)
│   ├── /curriculum            (Quiz banks, assignments)
│   ├── /coding                (Code challenges, test cases)
│   ├── /reports               (Analytics dashboards)
│   ├── /audit                 (Audit logs)
│   └── /settings              (Org settings)
│
├── /mentor
│   ├── /dashboard             (Mentor home)
│   ├── /submissions           (Student answers waiting review)
│   └── /reviews/[reviewId]    (Review interface for mentor comments)
│
├── /kt
│   ├── /dashboard             (KT home: my docs, recent chat)
│   ├── /documents             (Document library)
│   ├── /documents/create      (Create new KT doc)
│   ├── /documents/[docId]/edit (Edit draft)
│   ├── /documents/[docId]/review (Reviewer view)
│   ├── /chat/[sessionId]      (Chat with knowledge bot)
│   └── /chat/new              (Start new chat session)
│
├── /profile/[slug]            (Public learner profile)
├── /gradebook/[bankId]        (Gradebook: attempt stats by bank)
├── /leaderboard               (Quiz leaderboard)
├── /platform                  (Platform operator dashboard)
└── /[slug]                    (Catch-all: public content pages, org pages)
```

### 4.2 God Component Decomposition

#### **LDAdminDashboard (2,977 lines → 10 files)**

Current structure: 1 component with 10 tabs (tabs.tsx pattern or route-based)

**Target:**
```
apps/web-next/src/app/admin/
├── layout.tsx                 # Shared admin layout (sidebar nav)
├── page.tsx                   # Dashboard home (stats, quick links)
├── dashboard/
│   ├── page.tsx               # Overview dashboard
│   └── components/
│       ├── StatCard.tsx
│       ├── RecentActivityCard.tsx
│       └── OrgChart.tsx
├── hierarchy/
│   ├── page.tsx               # Org tree CRUD
│   └── components/
│       ├── OrgTreeExplorer.tsx
│       ├── OrgUnitForm.tsx
│       └── MoveUnitDialog.tsx
├── users/
│   ├── page.tsx               # User management
│   └── components/
│       ├── UserTable.tsx
│       ├── UserForm.tsx
│       └── BulkImportDialog.tsx
├── curriculum/
│   ├── page.tsx               # Question banks
│   └── components/
│       ├── BankList.tsx
│       ├── BankEditor.tsx
│       └── AssignmentForm.tsx
├── coding/
│   ├── page.tsx               # Coding challenges
│   └── components/
│       ├── CodingList.tsx
│       ├── CodingEditor.tsx
│       └── TestCaseBuilder.tsx
├── reports/
│   ├── page.tsx               # Reports & analytics
│   └── components/
│       ├── LeaderboardChart.tsx
│       ├── PerformanceMetrics.tsx
│       └── ExportButton.tsx
├── audit/
│   ├── page.tsx               # Audit logs
│   └── components/
│       └── AuditLogTable.tsx
└── settings/
    ├── page.tsx               # Org settings
    └── components/
        ├── OrgSettingsForm.tsx
        └── BrandingUpload.tsx
```

Each file <400 lines. Shared components in a common folder.

#### **UserProfile (1,227 lines → 3-4 files)**

```
apps/web-next/src/app/profile/[slug]/
├── page.tsx                   # Public profile view
├── edit/page.tsx              # (if own profile) Edit my profile
└── components/
    ├── ProfileHeader.tsx      # Avatar, name, role
    ├── SkillsSection.tsx      # Skills, badges, certificates
    ├── ActivityTimeline.tsx   # Recent quiz attempts, completions
    └── ProfileEditForm.tsx
```

#### **KTCreationWizard (983 lines → 4-5 files)**

```
apps/web-next/src/app/kt/documents/create/
├── page.tsx                   # Wizard orchestrator
├── steps/
│   ├── DetailsStep.tsx        # Doc type, title, description
│   ├── ContentStep.tsx        # Upload/paste content
│   ├── MetadataStep.tsx       # Domain, complexity, sensitivity
│   └── ReviewStep.tsx         # Preview before submit
└── hooks/
    └── useKTWizard.ts         # State management (Zustand or Context)
```

**State pattern:**
```typescript
// hooks/useKTWizard.ts
interface WizardState {
  step: 'details' | 'content' | 'metadata' | 'review';
  formData: KTDocumentCreate;
  errors: Record<string, string>;
}

export const useKTWizard = create<WizardState>((set) => ({
  step: 'details',
  formData: {},
  errors: {},
  setStep: (step) => set({ step }),
  setFormData: (data) => set({ formData: { ...current.formData, ...data } }),
  // ...
}));
```

#### **Dashboard (786 lines → 2-3 files)**

```
apps/web-next/src/app/dashboard/
├── page.tsx                   # Learner dashboard container
└── components/
    ├── MyExamsCard.tsx        # Assigned exams, upcoming
    ├── MyProgressCard.tsx     # Learning progress, badges
    ├── RecentAttemptsCard.tsx # Last 5 attempts
    └── RecommendationsCard.tsx # AI-suggested next steps
```

### 4.3 API Client: Typed + React Query

**Current:** `ApiService.ts` singleton (1,721 lines, 258 methods, Promise<any>).

**Target:** Type-safe, React Query hooks, automatic retry/caching.

**Structure:**
```
apps/web-next/src/services/
├── api/
│   ├── client.ts              # Axios instance, auth headers, error handling
│   ├── types.ts               # All API request/response types (auto-generated from backend?)
│   └── endpoints/
│       ├── auth.ts            # POST /login, /register, /refresh
│       ├── quiz.ts            # GET/POST /quiz/banks, /exam/*, /attempt/*
│       ├── kt.ts              # GET/POST /kt/documents, /kt/chat, /kt/projects
│       ├── org.ts             # GET/POST /org/units, /users
│       ├── admin.ts           # Admin endpoints
│       ├── reports.ts         # Analytics, exports
│       └── ...
│
├── hooks/
│   ├── useAuth.ts             # useLogin, useLogout, useRefreshToken
│   ├── useQuiz.ts             # useExams, useAttempt, useSubmitAnswers
│   ├── useKT.ts               # useDocuments, useChat, useProjectMembers
│   ├── useOrg.ts              # useOrgUnits, useUsers
│   ├── useReports.ts          # useLeaderboard, usePerformanceMetrics
│   └── usePagination.ts       # Shared pagination hook
│
└── queryClient.ts             # React Query config
```

**Example:**
```typescript
// services/api/endpoints/quiz.ts
import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from './client';

export const quizKeys = {
  all: ['quiz'] as const,
  banks: () => [...quizKeys.all, 'banks'],
  bank: (id: number) => [...quizKeys.banks(), id],
};

export const useExams = (orgId: number) =>
  useQuery({
    queryKey: ['exams', orgId],
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/quiz/exams?org_id=${orgId}`);
      return data as ExamListResponse;
    },
    staleTime: 5 * 60 * 1000, // 5 min
  });

export const useCreateExam = () =>
  useMutation({
    mutationFn: async (payload: ExamCreateRequest) => {
      const { data } = await apiClient.post('/api/quiz/exams', payload);
      return data as ExamResponse;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exams'] });
    },
  });
```

### 4.4 Single Design System

**Current:** Tailwind v4 (main app) + styled-jsx (KT sub-app).

**Target:** Tailwind v4 everywhere (no styled-jsx).

**Shared UI Kit:**
```
apps/web-next/src/components/ui/
├── Button.tsx                 # Generic button
├── Card.tsx                   # Card wrapper
├── Modal.tsx                  # Modal dialog
├── Tabs.tsx                   # Tab group
├── Form.tsx                   # Form layout
├── Input.tsx                  # Text input + variants
├── Select.tsx                 # Dropdown
├── DataTable.tsx              # Table with sort/filter
├── Dialog.tsx                 # Modal (shadcn/ui style)
├── Toast.tsx                  # Toast notifications
├── Breadcrumbs.tsx
├── Pagination.tsx
├── LoadingSpinner.tsx
└── ...
```

**Theme/Tokens:**
```typescript
// utils/theme.ts
export const colors = {
  primary: '#0066cc',
  secondary: '#666666',
  success: '#28a745',
  error: '#dc3545',
  warning: '#ffc107',
  neutral: {
    50: '#f5f5f5',
    100: '#eeeeee',
    200: '#e0e0e0',
    // ...
  },
};

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '16px',
  lg: '24px',
  xl: '32px',
};
```

---

## 5. API SURFACE RATIONALIZATION: 314 → ~200 ENDPOINTS

### 5.1 Endpoint Audit

**Current:** 314 endpoints, many duplicates, unclear scoping.

**Target:** ~200 stable endpoints, organized by module + resource.

**Strategy:**
1. Keep endpoints that work (quiz, exam, auth flows)
2. Delete deprecated/dead (system.py legacy, unused KT endpoints)
3. Merge duplicates (e.g., two "create_document" endpoints with different signatures)
4. Standardize naming:
   - GET `/api/module/resources` → list
   - POST `/api/module/resources` → create
   - GET `/api/module/resources/{id}` → detail
   - PUT `/api/module/resources/{id}` → update
   - DELETE `/api/module/resources/{id}` → delete

### 5.2 Endpoint Mapping (by module)

| Module | Est. Endpoints | Examples |
|---|---|---|
| **Platform** (super_org) | ~15 | `GET /platform/super-orgs`, `POST /platform/super-orgs`, billing hooks |
| **Identity** (auth, profile, roles) | ~25 | `/login`, `/register`, `/profile`, `/roles/assign` |
| **Org** (hierarchy, users) | ~30 | `/org/units` (CRUD), `/org/units/{id}/users`, `/org/units/{id}/children` |
| **Assessment** (quiz, exam, coding, mentor) | ~80 | `/quiz/banks`, `/exam/{id}/start`, `/attempt/{id}/submit`, `/coding/{id}/execute`, `/mentor/submissions/{id}/review` |
| **KT** (documents, chat, review) | ~50 | `/kt/documents` (CRUD), `/kt/documents/{id}/submit`, `/kt/documents/{id}/review`, `/kt/chat`, `/kt/projects` |
| **AI** (LLM, meter) | ~15 | `/ai/generate`, `/ai/meter/usage` |
| **Reporting** (quiz, KT, audit) | ~40 | `/reports/leaderboard`, `/reports/performance`, `/reports/export`, `/audit/logs` |
| **Jobs** (async) | ~5 | `GET /jobs/{id}/status` |
| **Misc** (contact, resources) | ~5 | `/contact`, `/resources` |
| **TOTAL** | ~265 | |

**Deletions:**
- `system.py` (~10 endpoints) → delete (legacy monitoring)
- Duplicate endpoints (audit all)
- Unused mentor endpoints (consolidate into single mentor module)
- Broken KT endpoints (replaced by new ingestion_service)

### 5.3 Versioning Convention

**Current:** No versioning (API is v0, everything breaks together).

**Target:** URL-based versioning (future-proofing only; don't over-engineer now).

```
/api/v1/                       # Current stable (2026-07-22 baseline after migration)
  /quiz
  /exam
  /kt
  ...

/api/v2/                       # Future breaking changes (if needed, 2027+)
  ...
```

All Phase 1-7 endpoints live under `/api/v1/`.

---

## 6. MIGRATION SEQUENCING: 8 PHASES

### Overview

| Phase | Duration | Focus | Parallel Streams | Risk |
|---|---|---|---|---|
| **Phase 1** | 2 weeks | Foundation: async DB session, modular structure, OrgUnit intro | Backend only | Low (backward compat) |
| **Phase 2** | 2.5 weeks | KT re-arch (pgvector), split kt.py routers | Backend; FE can prep | Medium (KT only) |
| **Phase 3** | 2 weeks | Split auth.py, quiz.py, admin.py; frontend starts routing | Both | Medium (backward compat) |
| **Phase 4** | 2 weeks | Frontend routing complete, new API client | FE focus | Medium (routing) |
| **Phase 5** | 1.5 weeks | Migration script: old org tables → OrgUnit; flip all queries | Both | High (data migration) |
| **Phase 6** | 1 week | Clean up: old KT services, god components finished, unused code | Both | Low (no new logic) |
| **Phase 7** | 1 week | Remove deprecated tables/code, final verification | Both | Low |
| **Phase 8** | 0.5 week | Deploy to production, monitor | Both | Medium (prod) |

**Total:** ~13 weeks, ~1 person-year effort (if 2 people: 6-7 weeks). Phases can overlap.

---

### Phase 1: FOUNDATION (2 weeks)

**Goal:** Set up modular backend structure, unified async DB pattern, OrgUnit introduction.

**Backend Tasks:**
1. [ ] Create `modules/` directory structure + `__init__.py` files
2. [ ] Create `shared/` folder: `exceptions.py`, `middleware.py`, `permissions.py`, `validators.py`
3. [ ] Refactor `database.py`:
   - [ ] Remove sync session factory (keep async only)
   - [ ] Add `get_db()` async dependency
   - [ ] Add connection pool tuning (serverless?)
4. [ ] Refactor `auth_utils.py`:
   - [ ] Move JWT decode to `modules/identity/services/auth_service.py`
   - [ ] Move org scoping to `modules/org/services/role_scope_service.py`
5. [ ] Create `modules/identity/models.py` + `modules/identity/services/`
   - [ ] Move `User`, `UserRole`, `Group` model definitions
   - [ ] Create `UserService`, `AuthService` classes
6. [ ] Create `modules/org/models.py`:
   - [ ] Add `OrgUnit`, `UserOrgRole` models
   - [ ] Create Alembic migration to add tables (keep old ones)
7. [ ] Create `shared/compatibility.py`:
   - [ ] Compatibility layer to read old OR new org structure
   - [ ] Allow both paths to work temporarily
8. [ ] Backfill script: `Department` → `OrgUnit(type=DEPARTMENT)`, etc.
   - [ ] One-time, idempotent script
   - [ ] Verify data integrity

**Frontend Tasks:**
1. [ ] Audit `ApiService.ts`: list all 258 methods by endpoint
2. [ ] Identify which endpoints will change (routers only; responses stay same for now)
3. [ ] Plan type generation from backend (OpenAPI? Pydantic JSON schema?)
4. [ ] Create `services/queryClient.ts` + React Query config

**Database Changes:**
```sql
-- New tables (no deletes)
CREATE TABLE org_units (...);
CREATE TABLE user_org_roles (...);
CREATE TABLE kt_document_chunks (...);
ALTER TABLE kt_documents ADD COLUMN org_id INT;
-- More migrations...
```

**Deliverables:**
- [ ] Backend compiles with new module structure
- [ ] All routers still work (backward compat)
- [ ] Tests pass (unit + integration)
- [ ] OrgUnit table created, backfill script runs
- [ ] Compatibility layer allows old + new queries to work

**Risk:** Low (additive changes, no deletions)

---

### Phase 2: KT RE-ARCHITECTURE (2.5 weeks)

**Goal:** Replace broken Neo4j pipeline with pgvector. Split kt.py.

**Backend Tasks:**
1. [ ] Install pgvector extension + SQLAlchemy support
2. [ ] Create `KTDocumentChunk` model + migration
3. [ ] Implement `modules/kt/services/ingestion_service.py`:
   - [ ] Document parsing (PDF, Markdown, TXT)
   - [ ] Text chunking (with overlap)
   - [ ] Batch embedding (Gemini API)
   - [ ] pgvector insertion
   - [ ] Error handling + retry logic
4. [ ] Implement `modules/kt/services/rag_service.py`:
   - [ ] pgvector similarity search
   - [ ] RAG prompt construction
   - [ ] LLM streaming
   - [ ] Chat message logging
5. [ ] Split `routers/kt.py` (3,893 lines) into:
   - [ ] `modules/kt/routers/documents.py` (~600 lines)
   - [ ] `modules/kt/routers/review.py` (~400 lines)
   - [ ] `modules/kt/routers/ingestion.py` (~300 lines)
   - [ ] `modules/kt/routers/chat.py` (~500 lines)
   - [ ] `modules/kt/routers/access.py` (~200 lines)
   - [ ] `modules/kt/routers/projects.py` (~400 lines)
   - [ ] `modules/kt/routers/handoff.py` (~300 lines)
   - [ ] (audit endpoints move to reporting module)
6. [ ] Create `modules/kt/models.py` + consolidate enums
7. [ ] Update `main.py` to register new KT routers
8. [ ] Remove dependency on Neo4j driver (leave DB, stop querying)

**Testing:**
- [ ] Unit tests: chunking, embedding, pgvector queries
- [ ] Integration tests: full ingest pipeline (mock S3, Gemini)
- [ ] E2E: upload document → chat over it
- [ ] Performance: query latency (<200ms for top-5 similarity)

**Deliverables:**
- [ ] KT ingestion pipeline fully functional on pgvector
- [ ] Chat works over new chunks
- [ ] Old kt.py routers split + integrated
- [ ] Tests covering happy path + error cases
- [ ] Migration from Neo4j (no-op, data was empty anyway)

**Risk:** Medium (core product change; chat is a key feature)

---

### Phase 3: SPLIT MONOLITH ROUTERS (2 weeks)

**Goal:** Break up remaining god files (auth.py, quiz.py, admin.py). Stabilize backend.

**Backend Tasks:**
1. [ ] Split `routers/auth.py` (2,381 lines):
   - [ ] `modules/identity/routers/auth.py` (~1,100 lines: login, register, refresh, logout, 2FA stub)
   - [ ] `modules/identity/routers/roles.py` (~200 lines: role CRUD, assignment)
   - [ ] Move profile to `modules/identity/routers/profile.py`
2. [ ] Split `routers/quiz.py` (2,119 lines):
   - [ ] `modules/assessment/routers/quiz.py` (~900 lines: bank CRUD, exam creation)
   - [ ] `modules/assessment/routers/exam.py` (~400 lines: exam attempt lifecycle)
3. [ ] Split `routers/admin.py` (814 lines):
   - [ ] `modules/org/routers/hierarchy.py` (~500 lines: org unit CRUD)
   - [ ] `modules/org/routers/users.py` (~300 lines: user assignments)
   - [ ] (audit queries move to `modules/reporting/routers/audit.py`)
4. [ ] Split `routers/reports.py` (1,861 lines):
   - [ ] `modules/reporting/routers/quiz_reports.py` (~1,000 lines)
   - [ ] `modules/reporting/routers/performance.py` (~400 lines)
   - [ ] `modules/reporting/routers/audit.py` (~300 lines)
5. [ ] Split `routers/ai.py` (1,119 lines):
   - [ ] `modules/ai/routers/ai.py` (~500 lines: LLM calls)
   - [ ] `modules/ai/routers/meter.py` (~200 lines: usage tracking)
6. [ ] Create service classes for each split router:
   - [ ] `AuthService`, `UserService`, `QuizService`, `ExamService`, `OrgService`, etc.
   - [ ] Move business logic from routers into services
7. [ ] Consolidate remaining routers:
   - [ ] `modules/assessment/routers/coding.py` (from code.py)
   - [ ] `modules/assessment/routers/mentor.py` (from mentor.py; defer major refactor to Phase 5)
   - [ ] `modules/assessment/routers/assignment.py` (from assignment.py)
   - [ ] `modules/platform/routers/super_org.py` (from platform.py)
   - [ ] `modules/platform/routers/contact.py`, `resources.py` (small, mostly as-is)
8. [ ] Ensure all routers use async/await consistently
9. [ ] Update `main.py` to register all new routers

**Frontend Tasks (parallel):**
1. [ ] Begin planning routing map
2. [ ] Create `apps/web-next/src/app/` directory structure matching target
3. [ ] No code yet; just structure + comments

**Testing:**
- [ ] All endpoints still respond (backward compat)
- [ ] No logic changes; only file reorganization
- [ ] Unit tests for each service class

**Deliverables:**
- [ ] Backend is now modular: each domain has its own routers + services
- [ ] No god files remain (all <800 lines)
- [ ] Full test coverage maintained

**Risk:** Medium (large refactor, but logic doesn't change)

---

### Phase 4: FRONTEND ROUTING + API CLIENT (2 weeks)

**Goal:** Replace state-machine SPA with real Next.js App Router. Build typed API client.

**Frontend Tasks:**
1. [ ] Implement `services/api/client.ts`:
   - [ ] Axios instance with auth headers
   - [ ] Error handling + token refresh
   - [ ] Base URL from env
2. [ ] Generate types from backend:
   - [ ] Option A: OpenAPI schema export from FastAPI + codegen
   - [ ] Option B: Manual type extraction from Pydantic schemas (faster for now)
   - [ ] Create `services/api/types.ts` with all request/response types
3. [ ] Create `services/hooks/` hooks for React Query:
   - [ ] `useAuth.ts`: login, logout, refresh
   - [ ] `useQuiz.ts`: exams, banks, questions
   - [ ] `useKT.ts`: documents, chat, projects
   - [ ] `useOrg.ts`: org units, users
   - [ ] `useReports.ts`: leaderboard, performance
4. [ ] Implement routing (replace state machine):
   - [ ] `/app/layout.tsx`: root layout (auth check, nav)
   - [ ] `/app/page.tsx`: home (redirect to dashboard or login)
   - [ ] `/app/dashboard/page.tsx`: learner home
   - [ ] `/app/exam/[id]/page.tsx`: take exam
   - [ ] `/app/exam/result/[attemptId]/page.tsx`: results
   - [ ] `/app/admin/layout.tsx` + sub-pages (dashboard, hierarchy, users, etc.)
   - [ ] `/app/mentor/layout.tsx` + sub-pages
   - [ ] `/app/kt/layout.tsx` + sub-pages (documents, chat, projects)
   - [ ] `/app/profile/[slug]/page.tsx`: public profile
   - [ ] `/app/platform/page.tsx`: platform admin
5. [ ] Decompose god components:
   - [ ] LDAdminDashboard → `/app/admin/` sub-components
   - [ ] UserProfile → `/app/profile/[slug]/` components
   - [ ] KTCreationWizard → `/app/kt/documents/create/` wizard steps
   - [ ] Dashboard → `/app/dashboard/` sub-cards
6. [ ] Implement shared UI kit in `components/ui/`
7. [ ] Remove state machine logic from `page.tsx`
8. [ ] Remove `ApiService.ts` (replace with React Query hooks)

**Backend (minimal changes):**
1. [ ] Add CORS headers if not present
2. [ ] Verify all endpoints return correct JSON structure
3. [ ] No schema changes

**Testing:**
- [ ] Routes work (navigation, deep-linking)
- [ ] API calls through new client work
- [ ] Auth flow (login → token → request → refresh)
- [ ] No regressions in exam flow or KT chat

**Deliverables:**
- [ ] All pages have real URLs (no state machine)
- [ ] API client is typed and uses React Query
- [ ] God components are decomposed
- [ ] Deep-linking works (copy URL → share → works)
- [ ] Back button, refresh work

**Risk:** Medium (routing change affects all flows; test thoroughly)

---

### Phase 5: DATA MIGRATION: ORGUNITS (1.5 weeks)

**Goal:** Migrate all org hierarchy logic from old tables to OrgUnit. Flip permission queries.

**Backend Tasks (high risk, execute carefully):**
1. [ ] Verify Phase 4 frontend is 100% working (don't migrate while FE is in flux)
2. [ ] Data audit:
   - [ ] Count old org entities (Department, Vertical, Batch, Group)
   - [ ] Verify all users have roles
   - [ ] Check for orphaned entities
3. [ ] Flip permission scoping:
   - [ ] Update `role_scope_service.py` to query `OrgUnit` first, fall back to old tables only if not found
   - [ ] Update all routers to use new queries
   - [ ] Test permission checks in all admin workflows
4. [ ] Update queries:
   - [ ] `get_user_org_units()`: query `UserOrgRole` + `OrgUnit`, not old `UserRole`
   - [ ] `get_descendant_units()`: use recursive CTE on `OrgUnit.parent_id`, not 5 separate table joins
   - [ ] `assign_user_to_group()`: insert to `UserOrgRole`, not old `UserRole`
5. [ ] Remove `KTCompany` usage:
   - [ ] Update KT endpoints to use `org_id` (from OrgUnit) instead of `company_id` (from old KTCompany)
   - [ ] Migration: map old `kt_documents.company_id` → `kt_documents.org_id`
6. [ ] Backfill script v2 (idempotent):
   - [ ] Any new Department/Vertical/Batch/Group created in old tables → add to OrgUnit
   - [ ] Any new UserRole assignments → add to UserOrgRole
7. [ ] Run data validation:
   - [ ] Every user assigned to a group in old system has corresponding UserOrgRole
   - [ ] No duplicates in new tables
   - [ ] Permission checks return same results (old vs. new path)

**Frontend Tasks (minimal):**
1. [ ] Verify org hierarchy display still works (no schema change, just backend internals)
2. [ ] Test admin user management flows

**Testing (critical):**
- [ ] Unit: `get_descendant_units()` for all hierarchy levels
- [ ] Integration: permission checks for all roles (learner, mentor, admin, ld_admin)
- [ ] E2E: create user → assign to batch → take exam → see in gradebook (old chain still works)
- [ ] Audit: compare query results (old permission method vs. new) for 1,000 random users

**Deliverables:**
- [ ] All org queries use OrgUnit + UserOrgRole
- [ ] Old tables remain (for safety), but all code reads new tables
- [ ] Data validation passes (no orphaned entities, no permission mismatches)

**Risk:** High (data migration is risky; have a rollback plan)

---

### Phase 6: CLEANUP + DECOMPOSE REMAINING GODS (1 week)

**Goal:** Delete dead code, finish decomposing remaining large components.

**Backend Tasks:**
1. [ ] Delete dead files:
   - [ ] `apps/api/fix_kt.py`
   - [ ] `apps/api/auto_fix_pyright_2.py`
   - [ ] `apps/api/check_users.py`
   - [ ] `apps/api/system.py` (legacy monitoring)
   - [ ] `services/kt_engine.py` (mostly; keep minimal helpers if needed)
   - [ ] `services/kt_langraph.py` (entire file)
   - [ ] `services/kt_workflows.py` (entire file)
   - [ ] Root clutter: `*.txt`, `*.zip`, temp scripts
2. [ ] Remove Neo4j references:
   - [ ] Remove `neo4j` package from `requirements.txt`
   - [ ] Remove Neo4j connection logic from `database.py`
   - [ ] Remove Neo4j queries from remaining services
3. [ ] Refactor `mentor.py` (1,017 lines → still large):
   - [ ] Split mentor review from quiz grading (currently mixed)
   - [ ] Create separate `MentorService` for mentor comment workflows
   - [ ] Reduce to <600 lines
4. [ ] Consolidate error handling:
   - [ ] All endpoints use custom exceptions from `shared/exceptions.py`
   - [ ] Consistent HTTP status codes
   - [ ] Error logging standardized
5. [ ] Documentation:
   - [ ] Add docstrings to all services
   - [ ] Create README.md for each module

**Frontend Tasks:**
1. [ ] Decompose `KTCreationWizard` → multi-file wizard (Phase 4 laid groundwork)
2. [ ] Convert remaining god components:
   - [ ] `LDAdminDashboard` → multiple pages under `/admin`
   - [ ] `UserProfile` → `/profile/[slug]` pages
   - [ ] `Dashboard` → `/dashboard/` component tree
3. [ ] Remove `styled-jsx` usage:
   - [ ] Audit all `.tsx` files for `<style jsx>` tags
   - [ ] Convert to Tailwind classes
4. [ ] Add error boundaries:
   - [ ] Top-level error boundary in layout
   - [ ] Section-level boundaries in complex pages
5. [ ] Remove unused components (from old state-machine SPA)

**Testing:**
- [ ] No regressions from code deletion
- [ ] All flows still work end-to-end

**Deliverables:**
- [ ] No god files remain (all <600 lines)
- [ ] Dead code deleted
- [ ] Clean, documented codebase
- [ ] Single design system (Tailwind only)

**Risk:** Low (cleanup, no new logic)

---

### Phase 7: ARCHIVE OLD TABLES (1 week)

**Goal:** Finalize org hierarchy migration, prepare for potential table cleanup.

**Backend Tasks:**
1. [ ] Write final validation script:
   - [ ] Verify no queries use old `Department`, `Vertical`, `Batch`, `Group`, `UserRole` tables
   - [ ] Audit logs show no access to old tables in production
2. [ ] Create archival migration:
   - [ ] Mark old tables as "deprecated" (add comment in migration)
   - [ ] Do NOT delete (keep for legal/audit trail)
   - [ ] Option: Move old tables to `archive_*` schema (if DB supports)
3. [ ] Update model imports:
   - [ ] Remove old entity imports from `models/__init__.py`
   - [ ] Keep archived classes available (commented out, for reference)
4. [ ] Performance tuning:
   - [ ] Verify index on `org_units(organization_id, parent_id)` exists
   - [ ] Verify index on `user_org_roles(user_id, org_unit_id)` exists
   - [ ] Query plan analysis for large orgs (1,000+ units)
5. [ ] Database backup:
   - [ ] Full backup before cleanup
   - [ ] Procedure to restore if needed

**Frontend:** No changes.

**Testing:**
- [ ] All hierarchies still render correctly
- [ ] Bulk user assignment still works
- [ ] Permission queries performant at scale

**Deliverables:**
- [ ] Production-ready org hierarchy
- [ ] Old tables archived (safe to delete later)
- [ ] No code references to old tables

**Risk:** Low (archival, not deletion)

---

### Phase 8: PRODUCTION DEPLOYMENT (0.5 week)

**Goal:** Deploy all changes to production, monitor, iterate.

**Deployment Checklist:**
1. [ ] Database migrations run in production (OrgUnit, UserOrgRole, KTDocumentChunk)
2. [ ] Backend code deployed (new modules, service split)
3. [ ] Frontend code deployed (new routing, API client)
4. [ ] Smoke tests:
   - [ ] Login works
   - [ ] Create quiz, take exam, submit
   - [ ] Upload KT doc, chat over it
   - [ ] Admin views load
   - [ ] Reports generate
5. [ ] Monitor:
   - [ ] Error rates in logs
   - [ ] API latency (target: <200ms p95)
   - [ ] Database connection pool usage
   - [ ] Redis cache hit rates
6. [ ] Rollback plan (if needed):
   - [ ] Revert frontend (easy: static assets)
   - [ ] Revert backend (more complex: DB rollback needed)
   - [ ] Communication plan to users

**Deliverables:**
- [ ] System running on new architecture
- [ ] Monitoring in place
- [ ] Zero-downtime deployment (use blue-green if possible)

**Risk:** Medium (production always risky; have rollback ready)

---

## 7. RISKS & OPEN QUESTIONS

### 7.1 Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **KT chat regression** | High | Phase 2 fully tested; old Neo4j disabled only after verified |
| **Org hierarchy corruption** | High | Data audit + validation script + backup + slow rollout |
| **Frontend routing breaks exams** | High | Phase 4 tested end-to-end before Phase 5 |
| **Auth token issues during migration** | Medium | Dual token strategies (old + new) in Phase 1-3 |
| **Performance regression (pgvector slow)** | Medium | Load test before Phase 2 deployment |
| **Database connection pool exhaustion** | Medium | Async session pooling tuned; monitor in Phase 8 |
| **Backward compatibility breaks** | Medium | Compatibility layer in Phase 1; test old + new paths |
| **Neo4j lingering issues** | Low | Leave DB alone (don't query); Phase 7 cleanup optional |

### 7.2 Open Questions

1. **API schema versioning:** Should we generate types from OpenAPI or maintain manually?
   - *Recommendation:* Manual for now (faster). OpenAPI in v2 if needed.

2. **Multi-region deployment:** Are we on Heroku, AWS, GCP? Any regional considerations?
   - *Dependency:* Affects async session pooling config, S3 region.

3. **Rate limiting:** Do we need it? Quiz API heavy usage?
   - *Recommendation:* Not in Phase 1; add in Phase 8+ if needed.

4. **Mentor workflow complexity:** mentor.py still 1K lines. How many mentor-specific features?
   - *Recommendation:* Defer deep refactor to Phase 6; focus on splitting.

5. **KT document approval:** Auto-approve (current plan) or require reviewer?
   - *Product decision:* Phase 2 assumes auto-approve; change if product wants manual review.

6. **Embedded vs. streaming RAG responses:** Phase 2 uses streaming. Bandwidth concern?
   - *Recommendation:* Stream by default (better UX); add buffering if needed.

7. **Old KTCompany vs. Organization:** Can these be truly merged, or legacy data issues?
   - *Risk assessment:* KT is mostly new data (Neo4j was empty); safe to merge.

8. **Analytics: performance_engine.py (1K lines):** Stays in assessment or move to reporting?
   - *Recommendation:* Move entire file to `modules/reporting/services/performance_service.py`.

---

## 8. SUMMARY: TARGET STATE

After Phase 8:

**Backend (apps/api):**
- Modular structure: 8 modules (platform, identity, org, assessment, kt, ai, reporting, jobs)
- No god files (all routers <700 lines, services <800 lines)
- Async DB sessions everywhere
- KT works end-to-end on pgvector
- Org hierarchy on unified OrgUnit tree
- ~200 stable, well-organized endpoints
- Full test coverage

**Frontend (apps/web-next):**
- Real URL routing (no state machine SPA)
- 8+ top-level routes (/dashboard, /admin/*, /kt/*, /profile, /exam, etc.)
- Typed API client with React Query
- Single design system (Tailwind v4)
- Decomposed god components (<400 lines each)
- Deep-linking works, back button works

**Data:**
- OrgUnit + UserOrgRole for hierarchy (replaces 5 tables)
- KTDocumentChunk + pgvector for RAG (replaces Neo4j)
- All learner data scoped correctly
- Neo4j decommissioned (archived, not deleted)

**Operations:**
- Faster development (clear boundaries, smaller files)
- Easier onboarding (modular structure, clear patterns)
- Lower maintenance burden (no god files, no dead code)
- Sustainable for 2-3 engineers

---

## CRITICAL FILES FOR IMPLEMENTATION

### Backend (Start Here)
1. **apps/api/database.py** — Async session setup (Phase 1)
2. **apps/api/main.py** — Router registration, middleware (all phases)
3. **apps/api/models/org.py** — OrgUnit + UserOrgRole schema (Phase 1)
4. **apps/api/models/kt_model.py** — KTDocumentChunk + consolidate KT entities (Phase 2)
5. **apps/api/modules/identity/services/auth_service.py** — JWT, token logic (Phase 1)
6. **apps/api/modules/kt/services/ingestion_service.py** — pgvector pipeline (Phase 2)
7. **apps/api/modules/kt/services/rag_service.py** — Chat logic (Phase 2)
8. **apps/api/modules/org/services/hierarchy_service.py** — OrgUnit tree ops (Phase 1)
9. **apps/api/migrations/versions/[next].py** — OrgUnit + chunks tables (Phase 1-2)
10. **apps/api/shared/exceptions.py** — Unified error handling (Phase 1)

### Frontend (Start Here)
1. **apps/web-next/src/app/layout.tsx** — Root layout, auth check (Phase 4)
2. **apps/web-next/src/app/page.tsx** — Replace state machine (Phase 4)
3. **apps/web-next/src/services/api/client.ts** — HTTP client (Phase 4)
4. **apps/web-next/src/services/api/types.ts** — Generated types (Phase 4)
5. **apps/web-next/src/services/hooks/useAuth.ts** — Auth React Query (Phase 4)
6. **apps/web-next/src/components/ui/Button.tsx** — Shared UI kit base (Phase 4)
7. **apps/web-next/src/app/admin/layout.tsx** — Admin route group (Phase 4)
8. **apps/web-next/src/app/kt/layout.tsx** — KT route group (Phase 4)

---

**END OF PLAN**

Status: Ready for implementation. Start with Phase 1 (2 weeks). Recommend running Phase 1 + Phase 2 in parallel after week 1 to save time.
