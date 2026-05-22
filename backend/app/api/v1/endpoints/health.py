from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.core.redis import redis_service
from loguru import logger

router = APIRouter()

@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint to test connection stability across database and redis services.
    """
    status = {
        "status": "healthy",
        "services": {
            "api": "online",
            "postgres": "offline",
            "redis": "offline"
        }
    }

    # 1. Test Postgres
    try:
        await db.execute(text("SELECT 1"))
        status["services"]["postgres"] = "online"
    except Exception as e:
        logger.error(f"Health check failed on Postgres: {e}")
        status["status"] = "unhealthy"

    # 2. Test Redis
    try:
        if redis_service.client:
            await redis_service.client.ping()
            status["services"]["redis"] = "online"
    except Exception as e:
        logger.error(f"Health check failed on Redis: {e}")
        status["status"] = "unhealthy"

    return status
