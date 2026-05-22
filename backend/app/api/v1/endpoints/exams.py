import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.exam import Exam
from app.schemas.v1.exam import ExamOut, ExamCreate, ExamGenerateRequest
from app.tasks.exam_tasks import generate_exam_task
from app.services.ai.exam_generation import exam_generation_service
from loguru import logger

router = APIRouter()

@router.get("", response_model=List[ExamOut])
async def list_exams(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Returns all examinations created by the currently logged-in user.
    """
    result = await db.execute(
        select(Exam).where(Exam.creator_id == current_user.id).order_by(Exam.created_at.desc())
    )
    return result.scalars().all()

@router.get("/{exam_id}", response_model=ExamOut)
async def get_exam(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Returns exam structure details containing questions and assessment rubrics.
    """
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
        
    if exam.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this exam")
        
    return exam

@router.post("/generate", status_code=202)
async def trigger_async_exam_generation(
    request: ExamGenerateRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Triggers asynchronous Celery task to generate questions.
    Returns the task_id which the frontend can subscribe to via WebSockets.
    """
    task_id = str(uuid.uuid4())
    
    # Send task to exam_queue
    generate_exam_task.apply_async(
        args=[
            str(current_user.id),
            str(request.document_id),
            request.title,
            request.num_questions,
            request.topic_focus,
            task_id
        ],
        task_id=task_id
    )
    
    logger.info(f"Triggered async exam generation task: {task_id} on exam_queue.")
    return {
        "status": "triggered",
        "task_id": task_id,
        "message": "Exam generation running in background worker."
    }

@router.post("/generate-sync", response_model=ExamOut)
async def generate_exam_synchronously(
    request: ExamGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Generates and saves questions synchronously. Useful for small testing or light documents.
    """
    try:
        # Call generation service directly
        questions_data = await exam_generation_service.generate_exam(
            session=db,
            document_id=request.document_id,
            title=request.title,
            num_questions=request.num_questions,
            topic_focus=request.topic_focus
        )
        
        # Save to DB
        exam = Exam(
            title=request.title,
            creator_id=current_user.id,
            document_id=request.document_id
        )
        db.add(exam)
        await db.flush() # populate ID
        
        from app.models.exam import Question
        for q_data in questions_data:
            question = Question(
                exam_id=exam.id,
                text=q_data["text"],
                expected_answer=q_data["expected_answer"],
                rubric=q_data["rubric"]
            )
            db.add(question)
            
        await db.commit()
        await db.refresh(exam)
        
        return exam
    except Exception as e:
        logger.error(f"Sync exam generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")
