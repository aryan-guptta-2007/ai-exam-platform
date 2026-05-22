import asyncio
import json
import uuid
import redis
from celery import shared_task
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.ai_orchestrator import document_ingestion_flow
from loguru import logger

def publish_ws_progress(task_id: str, status: str, percentage: int, message: str) -> None:
    """
    Synchronous Redis client publisher for Celery worker environment.
    """
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        payload = {
            "event": "progress",
            "task_id": task_id,
            "payload": {
                "status": status,
                "percentage": percentage,
                "message": message
            }
        }
        r.publish(f"task:{task_id}", json.dumps(payload))
    except Exception as e:
        logger.error(f"Failed to publish progress to Redis for task {task_id}: {e}")

async def run_async_ingestion(
    task_id: str,
    user_id: uuid.UUID,
    raw_text: str,
    filename: str,
    storage_path: str
) -> None:
    # Setup callback wrapper
    async def progress_cb(status: str, percentage: int, message: str) -> None:
        publish_ws_progress(task_id, status, percentage, message)
        
    async with AsyncSessionLocal() as session:
        try:
            await document_ingestion_flow.execute(
                session=session,
                user_id=user_id,
                raw_text=raw_text,
                filename=filename,
                storage_path=storage_path,
                progress_cb=progress_cb
            )
        except Exception as e:
            logger.error(f"Ingestion failed for task {task_id}: {e}")
            publish_ws_progress(task_id, "error", 100, f"Error processing file: {str(e)}")
            raise e

@shared_task(name="app.tasks.embedding_tasks.process_document_ingestion")
def process_document_ingestion(
    user_id_str: str,
    raw_text: str,
    filename: str,
    storage_path: str,
    task_id_override: str = None
) -> str:
    """
    Celery task running on embedding_queue.
    """
    # Use Celery request ID or override
    # celery request context is accessed via task self.request.id, 
    # but we can pass task_id_override for consistency
    task_id = task_id_override or str(uuid.uuid4())
    user_id = uuid.UUID(user_id_str)
    
    logger.info(f"Celery worker processing document ingestion task: {task_id}")
    publish_ws_progress(task_id, "starting", 0, "Ingestion task triggered in queue...")
    
    # Bootstrap async loop inside Celery sync thread
    asyncio.run(run_async_ingestion(task_id, user_id, raw_text, filename, storage_path))
    
    return task_id
