from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import redis_service
from app.core.database import AsyncSessionLocal
from app.vector_store.client import init_vector_extension
from app.api.v1.api import api_router
from loguru import logger

# Initialize structured logging
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    App Startup and Shutdown lifecycles.
    """
    # 1. Startup tasks
    logger.info("Initializing application startup sequence...")
    
    # Connect to Redis connection pool
    await redis_service.connect()
    
    # Initialize pgvector database extension (requires database connection)
    async with AsyncSessionLocal() as session:
        try:
            await init_vector_extension(session)
        except Exception as e:
            logger.error(f"Startup warning: pgvector initialization failed: {e}")
            
    yield
    
    # 2. Shutdown tasks
    logger.info("Initializing application shutdown sequence...")
    await redis_service.disconnect()

# Instantiate FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Production-grade AI-powered Exam Learning Platform Backend API.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS origins configured: {settings.BACKEND_CORS_ORIGINS}")

# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API. Access documentation at /docs"
    }
