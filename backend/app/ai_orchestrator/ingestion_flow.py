import uuid
from typing import Dict, Any, Callable, Awaitable, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai_orchestrator.base_flow import BaseAIWorkflow
from app.knowledge_engine.indexer import indexer
from app.models.document import Document, DocumentChunk
from app.analytics.tracker import analytics_tracker
from loguru import logger
import time

class DocumentIngestionWorkflow(BaseAIWorkflow):
    """
    Core IP Orchestration Flow. Coordinates:
    Upload -> Text Extraction -> Chunking -> Embedding -> Vector DB insertion -> Relationship analysis.
    """
    def __init__(self):
        super().__init__("DocumentIngestion")

    async def execute(
        self, 
        session: AsyncSession, 
        user_id: uuid.UUID,
        raw_text: str, 
        filename: str,
        storage_path: str,
        progress_cb: Callable[[str, int, str], Awaitable[None]] = None
    ) -> Document:
        start_time = time.time()
        logger.info(f"Executing ingestion flow for user {user_id}, file: {filename}")
        
        # Step 1: Initialize Document model in DB
        await self.broadcast_progress(progress_cb, "initializing", 10, "Initializing document record...")
        document = Document(
            title=filename,
            storage_path=storage_path,
            owner_id=user_id
        )
        session.add(document)
        await session.flush() # Populate document.id
        
        # Step 2: Extract, Chunk, Embed, and analyze relationships
        await self.broadcast_progress(progress_cb, "indexing", 30, "Splitting content and extracting topics...")
        
        # Wrap indexer call with retry logic
        doc_metadata, chunks_payload, relationships = await self.execute_with_retry(
            lambda: indexer.index_document(raw_text, filename)
        )
        
        # Step 3: Write chunks to Database
        await self.broadcast_progress(progress_cb, "saving_vectors", 70, "Inserting chunks and vector embeddings into database...")
        db_chunks = []
        for ch in chunks_payload:
            chunk_record = DocumentChunk(
                document_id=document.id,
                content=ch["content"],
                embedding=ch["embedding"],
                metadata_json={
                    **ch["metadata"],
                    "topics": doc_metadata.get("topics", [])
                }
            )
            db_chunks.append(chunk_record)
            session.add(chunk_record)
            
        # Commit to save all data
        await session.commit()
        
        # Step 4: Finished
        await self.broadcast_progress(progress_cb, "done", 100, "Document ingestion and indexing completed successfully.")
        
        latency = time.time() - start_time
        analytics_tracker.track_pipeline_latency(
            "document_ingestion", 
            latency, 
            {"document_id": str(document.id), "chunks": len(db_chunks)}
        )
        
        return document

document_ingestion_flow = DocumentIngestionWorkflow()
