from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

async def init_vector_extension(session: AsyncSession) -> None:
    """
    Enables the pgvector extension in the PostgreSQL database.
    Must be run by a user with superuser permissions.
    """
    try:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await session.commit()
        logger.info("Successfully checked/created pgvector extension in the database.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to initialize pgvector database extension: {e}")
        raise e
