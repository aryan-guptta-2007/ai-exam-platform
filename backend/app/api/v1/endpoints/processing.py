import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.storage import get_storage_provider
from app.tasks.embedding_tasks import process_document_ingestion
from loguru import logger

router = APIRouter()

@router.post("/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Ingest files.
    Reads file content, commits to storage, and queues ingestion tasks to Celery.
    Returns task_id which updates progress via WebSockets.
    """
    # Verify file is PDF or text
    filename = file.filename
    if not filename.endswith((".pdf", ".txt", ".ppt", ".pptx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload PDF, TXT, or PPT/PPTX files."
        )

    try:
        content = await file.read()
        
        # 1. Save file using storage provider abstraction
        storage = get_storage_provider()
        # Generate unique storage filename
        unique_name = f"{uuid.uuid4()}_{filename}"
        storage_path = await storage.save_file(content, unique_name)
        
        # Extract text representation
        # For actual PDFs, you would run pypdf / pdfplumber.
        # Here we mock text decoding for standard demo processing.
        try:
            raw_text = content.decode("utf-8")
        except UnicodeDecodeError:
            # Mock extracted text for binary formats in Layer 1 setup
            raw_text = (
                f"Extracted content card from uploaded slide/document {filename}.\n"
                "This document discusses concepts of operating systems, virtual memory, paging, "
                "context switching, and caching principles. Let's study how processes coordinate."
            )

        # 2. Trigger Celery Ingestion pipeline
        task_id = str(uuid.uuid4())
        process_document_ingestion.apply_async(
            args=[
                str(current_user.id),
                raw_text,
                filename,
                storage_path,
                task_id
            ],
            task_id=task_id
        )

        logger.info(f"Queued file ingestion task {task_id} on embedding_queue for file {filename}")
        return {
            "status": "queued",
            "task_id": task_id,
            "filename": filename,
            "storage_path": storage_path
        }
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"File uploading failed: {str(e)}")
