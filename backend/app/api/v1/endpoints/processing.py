import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.storage import get_storage_provider
from app.tasks.embedding_tasks import process_document_ingestion
from loguru import logger

router = APIRouter()

@router.post("/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest files.
    Reads file content, computes SHA256 hash to prevent duplicate ingestion,
    commits to storage, and queues ingestion tasks to Celery.
    Returns task_id which updates progress via WebSockets.
    """
    filename = file.filename
    if not filename.endswith((".pdf", ".txt", ".ppt", ".pptx", ".docx", ".md", ".html", ".htm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload PDF, TXT, PPT/PPTX, DOCX, MD, or HTML files."
        )

    try:
        content = await file.read()
        
        # 1. Compute SHA256 of uploaded file content
        import hashlib
        sha256_hash = hashlib.sha256(content).hexdigest()
        
        # 2. Check for duplicate document in DB
        from sqlalchemy import select
        from app.models.document import Document
        
        query = select(Document).where(Document.sha256 == sha256_hash)
        result = await db.execute(query)
        existing_doc = result.scalars().first()
        
        if existing_doc:
            logger.info(f"Duplicate document detected (SHA256: {sha256_hash}) for file {filename}. Skipping ingestion.")
            return {
                "status": "duplicate",
                "document_id": str(existing_doc.id),
                "filename": existing_doc.title,
                "storage_path": existing_doc.storage_path
            }

        # 3. Save file using storage provider abstraction
        storage = get_storage_provider()
        unique_name = f"{uuid.uuid4()}_{filename}"
        storage_path = await storage.save_file(content, unique_name)
        
        # 4. Trigger Celery Ingestion pipeline
        task_id = str(uuid.uuid4())
        process_document_ingestion.apply_async(
            args=[
                str(current_user.id),
                filename,
                storage_path,
                sha256_hash,
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
