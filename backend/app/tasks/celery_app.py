from celery import Celery
from app.core.config import settings

# Instantiate Celery
celery = Celery(
    "exam_platform_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery Configurations
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Configure task routing to separate queues/workers
    task_routes={
        "app.tasks.embedding_tasks.*": {"queue": "embedding_queue"},
        "app.tasks.teaching_tasks.*": {"queue": "teaching_queue"},
        "app.tasks.exam_tasks.*": {"queue": "exam_queue"},
        "app.tasks.email_tasks.*": {"queue": "email_queue"},
    },
    # Ensure worker prefetch limits are low for heavy AI workloads
    worker_prefetch_multiplier=1,
)

# Auto-discover task modules
celery.autodiscover_tasks([
    "app.tasks.embedding_tasks",
    "app.tasks.teaching_tasks",
    "app.tasks.exam_tasks",
    "app.tasks.email_tasks"
])
