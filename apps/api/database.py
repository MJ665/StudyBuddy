import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

env_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
)
load_dotenv(env_path)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set in the environment")

# Sync Engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=20,
    max_overflow=30,
    # Fail fast when the pool is saturated instead of hanging the request
    # indefinitely (surfaces overload as a clear 500 rather than a timeout).
    pool_timeout=30,
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async Engine
# Transform postgresql:// to postgresql+asyncpg:// and strip unsupported query params
ASYNC_DATABASE_URL = DATABASE_URL
if ASYNC_DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )

# STRAT-FIX: asyncpg does not accept 'sslmode'/'channel_binding' URL query params
# (they are libpq/psycopg2 concepts). Strip them, but REMEMBER whether SSL was
# requested so we can re-enable it via asyncpg's connect_args — managed Postgres
# providers (e.g. Neon) require TLS and will reject a plaintext connection.
_async_connect_args: dict = {}
if any(p in ASYNC_DATABASE_URL for p in ["sslmode=", "channel_binding="]):
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    u = urlparse(ASYNC_DATABASE_URL)
    query = dict(parse_qsl(u.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    ASYNC_DATABASE_URL = urlunparse(u._replace(query=urlencode(query)))
    # Any sslmode other than an explicit 'disable' means TLS is expected.
    if sslmode not in (None, "disable"):
        _async_connect_args["ssl"] = True

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    echo=False,
    connect_args=_async_connect_args,
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Alias for services that need it
db_session_factory = AsyncSessionLocal

Base = declarative_base()


# Sync dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Async dependency
async def get_async_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
        finally:
            pass
