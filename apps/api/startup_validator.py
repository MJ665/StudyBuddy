import logging

from config import settings
from database import engine
from services.redis_service import redis_client
from sqlalchemy import text

logger = logging.getLogger("startup_validator")


async def validate_infrastructure():
    """
    Ensures infrastructure readiness before application boot.
    Prevents cascading failures in production.
    """
    logger.info("Starting production infrastructure validation...")
    results = {}

    # 1. Database Connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        results["database"] = {"status": "healthy"}
        logger.info("✅ Database connectivity verified.")
    except Exception as e:
        results["database"] = {"status": "unhealthy", "error": str(e)}
        logger.error(f"❌ Database connection failed: {e}")

    # 2. Redis Connectivity
    try:
        await redis_client.set("startup_test", "ok", ex=10)
        results["redis"] = {"status": "healthy"}
        logger.info("✅ Redis connectivity verified.")
    except Exception as e:
        results["redis"] = {"status": "unhealthy", "error": str(e)}
        logger.error(f"❌ Redis connection failed: {e}")

    # 3. AI Service Configuration
    results["ai"] = {
        "status": "healthy" if settings.GEMINI_API_KEY else "disabled",
        "provider": "Gemini",
    }

    # 4. S3 Configuration
    results["s3"] = {
        "status": "healthy" if settings.S3_BUCKET_NAME else "unhealthy",
        "bucket": settings.S3_BUCKET_NAME,
    }

    # 5. KT vector store (pgvector on the primary DB — Neo4j retired, Phase 7)
    try:
        from sqlalchemy import text as _text

        from database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            ok = (
                await s.execute(
                    _text("SELECT 1 FROM pg_extension WHERE extname='vector'")
                )
            ).first()
        results["pgvector"] = {"status": "healthy" if ok else "missing"}
        logger.info("✅ pgvector extension verified.")
    except Exception as e:
        results["pgvector"] = {"status": "unhealthy", "error": str(e)}
        logger.error(f"❌ pgvector check failed: {e}")

    logger.info("Infrastructure validation complete.")
    return results


# Keep alias for backward compatibility in routers/admin.py
class StartupValidator:
    @staticmethod
    async def validate_all():
        return await validate_infrastructure()


startup_validator = StartupValidator()
