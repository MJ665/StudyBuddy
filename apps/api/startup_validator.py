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

    # 5. Neo4j Initialization
    try:
        from services.kt_engine import neo4j

        await neo4j.setup_constraints()
        results["neo4j"] = {"status": "healthy"}
        logger.info("✅ Neo4j constraints verified.")
    except Exception as e:
        results["neo4j"] = {"status": "unhealthy", "error": str(e)}
        logger.error(f"❌ Neo4j initialization failed: {e}")

    logger.info("Infrastructure validation complete.")
    return results


# Keep alias for backward compatibility in routers/admin.py
class StartupValidator:
    @staticmethod
    async def validate_all():
        return await validate_infrastructure()


startup_validator = StartupValidator()
