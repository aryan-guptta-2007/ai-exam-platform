import asyncio
import json
import uuid
import redis
from celery import shared_task
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.ai.exam_generation import exam_generation_service
from app.models.exam import Exam, Question
from loguru import logger

def publish_ws_progress(task_id: str, status: str, percentage: int, message: str) -> None:
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

async def run_async_exam_generation(
    task_id: str,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    title: str,
    num_questions: int,
    topic_focus: str = None
) -> None:
    publish_ws_progress(task_id, "retrieving", 20, "Searching relevant document sections...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Generate exam questions
            publish_ws_progress(task_id, "generating", 50, "Generating questions and grading rubrics using LLM...")
            
            questions_data = await exam_generation_service.generate_exam(
                session=session,
                document_id=document_id,
                title=title,
                num_questions=num_questions,
                topic_focus=topic_focus
            )
            
            # Save Exam and Questions to DB
            publish_ws_progress(task_id, "saving", 85, "Saving generated exam to database...")
            
            exam = Exam(
                title=title,
                creator_id=user_id,
                document_id=document_id
            )
            session.add(exam)
            await session.flush() # Populate exam.id
            
            for q_data in questions_data:
                question = Question(
                    exam_id=exam.id,
                    text=q_data["text"],
                    expected_answer=q_data["expected_answer"],
                    rubric=q_data["rubric"]
                )
                session.add(question)
                
            await session.commit()
            publish_ws_progress(task_id, "done", 100, f"Exam '{title}' successfully generated.")
            
        except Exception as e:
            logger.error(f"Exam generation task {task_id} failed: {e}")
            publish_ws_progress(task_id, "error", 100, f"Error generating exam: {str(e)}")
            raise e

@shared_task(name="app.tasks.exam_tasks.generate_exam_task")
def generate_exam_task(
    user_id_str: str,
    document_id_str: str,
    title: str,
    num_questions: int,
    topic_focus: str = None,
    task_id_override: str = None
) -> str:
    """
    Celery task running on exam_queue.
    """
    task_id = task_id_override or str(uuid.uuid4())
    user_id = uuid.UUID(user_id_str)
    document_id = uuid.UUID(document_id_str)
    
    logger.info(f"Celery worker processing exam generation task: {task_id}")
    publish_ws_progress(task_id, "starting", 5, "Triggering exam generation task...")
    
    asyncio.run(
        run_async_exam_generation(
            task_id, 
            user_id, 
            document_id, 
            title, 
            num_questions, 
            topic_focus
        )
    )
    
    return task_id
