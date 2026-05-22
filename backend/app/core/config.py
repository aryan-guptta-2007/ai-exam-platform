import json
from typing import List, Union
from pydantic import AnyHttpUrl, BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated

def validate_cors_origins(v: Union[str, List[str]]) -> List[str]:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, (list, str)):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v
    raise ValueError(v)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )

    # Core App Settings
    PROJECT_NAME: str = "AI Exam Learning Platform"
    ENV: str = "development"
    API_V1_STR: str = "/api/v1"
    
    # JWT Auth Configuration
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS Origins (Annotated with BeforeValidator for flexible list input parsing)
    BACKEND_CORS_ORIGINS: Annotated[
        List[str], BeforeValidator(validate_cors_origins)
    ] = []

    # Database Settings
    POSTGRES_SERVER: str = "db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "exam_platform"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/exam_platform"

    # Redis Settings
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://redis:6379/0"

    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # AI Config
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    PRIMARY_LLM_PROVIDER: str = "openai"
    FALLBACK_LLM_PROVIDER: str = "gemini"

    # Storage Config
    STORAGE_PROVIDER: str = "local"
    STORAGE_LOCAL_PATH: str = "./storage_uploads"
    S3_BUCKET_NAME: str = "exam-platform-assets"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"

    # Feature Flags
    ENABLE_DETAILED_COST_TRACKING: bool = True
    ENABLE_HALLUCINATION_VALIDATION: bool = True
    USE_HYBRID_RETRIEVAL: bool = True

settings = Settings()
