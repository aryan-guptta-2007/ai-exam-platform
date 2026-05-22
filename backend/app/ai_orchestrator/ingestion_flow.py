import uuid
from typing import Dict, Any, Callable, Awaitable, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai_orchestrator.base_flow import BaseAIWorkflow
from app.knowledge_engine.indexer import indexer
from app.models.document import Document, DocumentChunk, DocumentChunkRelationship
from app.analytics.tracker import analytics_tracker
from loguru import logger
import time

class DocumentIngestionWorkflow(BaseAIWorkflow):
    """
    Coordinates:
    Upload -> Document Parsing -> Chunking -> Embedding -> Vector DB insertion -> Relationship analysis & Graph creation.
    """
    def __init__(self):
        super().__init__("DocumentIngestion")

    async def execute(
        self, 
        session: AsyncSession, 
        user_id: uuid.UUID,
        filename: str,
        storage_path: str,
        sha256: str,
        progress_cb: Callable[[str, int, str], Awaitable[None]] = None
    ) -> Document:
        start_time = time.time()
        logger.info(f"Executing ingestion flow for user {user_id}, file: {filename}, sha256: {sha256}")
        
        # Step 1: Initialize Document model in DB
        await self.broadcast_progress(progress_cb, "initializing", 10, "Initializing document record...")
        document = Document(
            title=filename,
            storage_path=storage_path,
            owner_id=user_id,
            sha256=sha256
        )
        session.add(document)
        await session.flush() # Populate document.id
        
        # Step 2: Parse, Chunk, Embed, and analyze relationships
        await self.broadcast_progress(progress_cb, "indexing", 30, "Parsing document contents, chunking and generating embeddings...")
        
        # Wrap indexer call with retry logic
        doc_metadata, chunks_payload, relationships = await self.execute_with_retry(
            lambda: indexer.index_document(storage_path, filename)
        )
        
        # Step 3: Write chunks to Database
        await self.broadcast_progress(progress_cb, "saving_vectors", 70, "Inserting chunks and vector embeddings into database...")
        db_chunks = []
        for ch in chunks_payload:
            chunk_record = DocumentChunk(
                document_id=document.id,
                content=ch["content"],
                embedding=ch["embedding"],
                char_start=ch["metadata"].get("char_start"),
                char_end=ch["metadata"].get("char_end"),
                metadata_json={
                    **ch["metadata"],
                    "summary": doc_metadata.get("summary", ""),
                    "suggested_title": doc_metadata.get("suggested_title", filename),
                    "key_concepts": doc_metadata.get("key_concepts", []),
                    "subject": doc_metadata.get("subject", "General"),
                    "topic": doc_metadata.get("topic", "General"),
                    "chapter": doc_metadata.get("chapter", None),
                    "academic_domain": doc_metadata.get("academic_domain", "General"),
                    "language": doc_metadata.get("language", "English"),
                    "estimated_difficulty": doc_metadata.get("estimated_difficulty", "Medium")
                }
            )
            db_chunks.append(chunk_record)
            session.add(chunk_record)
            
        await session.flush() # Populate chunk IDs
        
        # Step 4: Write chunk relationships to Database
        logger.info(f"Persisting {len(relationships)} chunk relationships to database...")
        for rel in relationships:
            src_idx = rel["source_index"]
            tgt_idx = rel["target_index"]
            if src_idx < len(db_chunks) and tgt_idx < len(db_chunks):
                rel_record = DocumentChunkRelationship(
                    source_chunk_id=db_chunks[src_idx].id,
                    target_chunk_id=db_chunks[tgt_idx].id,
                    type=rel["type"],
                    weight=rel["weight"]
                )
                session.add(rel_record)
        
        # Commit to save all data
        await session.commit()
        
        # Step 5: Finished
        await self.broadcast_progress(progress_cb, "done", 100, "Document ingestion and indexing completed successfully.")
        
        latency = time.time() - start_time
        analytics_tracker.track_pipeline_latency(
            "document_ingestion", 
            latency, 
            {"document_id": str(document.id), "chunks": len(db_chunks)}
        )
        
        return document

document_ingestion_flow = DocumentIngestionWorkflow()
