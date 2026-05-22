from celery import shared_task
from loguru import logger
import uuid

@shared_task(name="app.tasks.teaching_tasks.process_teaching_task")
def process_teaching_task(user_id_str: str, topic: str) -> str:
    """
    Celery task running on teaching_queue.
    Used for long-running teaching jobs (e.g. compiling complete study guide PDFs).
    """
    task_id = str(uuid.uuid4())
    logger.info(f"Celery worker processing teaching task: {task_id} for user {user_id_str} on topic {topic}")
    return task_id
