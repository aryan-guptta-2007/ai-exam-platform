import asyncio
import uuid
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.models.cost import CostRecord
from app.ai_orchestrator.ingestion_flow import document_ingestion_flow
from app.core.security import get_password_hash
from app.cost_monitoring.monitor import cost_monitor
from loguru import logger

async def test_ingestion():
    logger.info("Starting End-to-End Pipeline Verification Test...")
    
    async with AsyncSessionLocal() as session:
        # 1. Create a test user if not exists
        email = "testuser@example.com"
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        user = result.scalars().first()
        
        if not user:
            logger.info("Creating a new test user...")
            user = User(
                email=email,
                hashed_password=get_password_hash("testpassword"),
                is_active=True,
                is_superuser=False
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logger.info(f"Test user created with ID: {user.id}")
        else:
            logger.info(f"Using existing test user ID: {user.id}")
            
        # 2. Define sample document text to ingest
        sample_text = (
            "Operating Systems: Virtual Memory and Paging.\n"
            "Virtual memory is a memory management technique that provides an idealized abstraction of the "
            "storage resources that are actually available on a given machine. Paging is a memory management "
            "scheme by which a computer stores and retrieves data from secondary storage for use in main memory. "
            "In this scheme, the operating system retrieves data from secondary storage in same-size blocks called pages. "
            "Virtual memory allows a computer to compensate for physical memory shortages, temporarily transferring "
            "data from random access memory (RAM) to disk storage. This process is seamless to the user.\n"
            "CPU Scheduling and Context Switching.\n"
            "CPU scheduling is the process of deciding which process will run on the CPU next. A context switch is the "
            "process of storing the state of a process or thread, so that it can be restored and resume execution at a "
            "later point. This allows multiple processes to share a single CPU and is an essential feature of multitasking."
        )
        
        filename = "operating_systems_notes.txt"
        storage_path = "./storage_uploads/test_os_notes.txt"
        
        # Define a mock progress callback
        async def mock_progress(status: str, progress: int, message: str):
            logger.info(f"Progress Callback -> status: {status}, progress: {progress}%, message: {message}")

        # 3. Execute the Ingestion Flow (orchestrator)
        logger.info("Triggering document ingestion flow...")
        document = await document_ingestion_flow.execute(
            session=session,
            user_id=user.id,
            raw_text=sample_text,
            filename=filename,
            storage_path=storage_path,
            progress_cb=mock_progress
        )
        
        logger.info(f"Ingestion flow executed. Document created with ID: {document.id}")
        
        # 4. Verify results in DB
        # Re-fetch document using a fresh query to verify it was committed
        stmt_doc = select(Document).where(Document.id == document.id)
        result_doc = await session.execute(stmt_doc)
        db_doc = result_doc.scalars().first()
        assert db_doc is not None, "Document not found in database!"
        logger.info("Assertion passed: Document exists in database.")
        
        # Check Chunks
        stmt_chunks = select(DocumentChunk).where(DocumentChunk.document_id == document.id)
        result_chunks = await session.execute(stmt_chunks)
        db_chunks = result_chunks.scalars().all()
        assert len(db_chunks) > 0, "No chunks created in database!"
        logger.info(f"Assertion passed: Found {len(db_chunks)} chunks in database.")
        
        # Verify embedding size and content
        for chunk in db_chunks:
            assert chunk.embedding is not None, "Embedding is null!"
            assert len(chunk.embedding) == 1536, f"Expected 1536 dimensions, got {len(chunk.embedding)}!"
            logger.info(f"Chunk ID {chunk.id} embedding has correct dimension (1536).")
            
        # Verify Cost record tracking (directly log cost to verify the table writes and logic)
        logger.info("Verifying Cost Monitoring Log integration...")
        cost_record = await cost_monitor.log_cost(
            session=session,
            user_id=user.id,
            model_name="gpt-4o-mini",
            prompt_tokens=450,
            completion_tokens=220,
            task_name="document_ingestion"
        )
        assert cost_record is not None, "Cost record failed to log!"
        logger.info(f"Cost record logged with ID: {cost_record.id}, estimated cost: {cost_record.estimated_cost:.6f} USD")
        
        # Confirm write in database
        stmt_cost = select(CostRecord).where(CostRecord.id == cost_record.id)
        result_cost = await session.execute(stmt_cost)
        db_cost = result_cost.scalars().first()
        assert db_cost is not None, "Cost record not found in database!"
        logger.info("Assertion passed: CostRecord exists in database.")
        
        logger.success("End-to-End Pipeline Verification Test COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_ingestion())
