import asyncio
import uuid
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.document import Document, DocumentChunk, DocumentChunkRelationship
from app.core.security import get_password_hash
from app.services.ai.embeddings import embedding_service
from app.core.redis import redis_service
from app.utils.parsers.pdf import PDFParser
from app.ai_orchestrator.ingestion_flow import document_ingestion_flow
from app.services.ai.retrieval import retrieval_service
from app.analytics.tracker import analytics_tracker
from loguru import logger

async def run_tests():
    logger.info("Initializing Layer 3 Integration Tests...")
    await redis_service.connect()
    try:
        async with AsyncSessionLocal() as session:
            # Create a test user
            email = "layer3test@example.com"
            stmt = select(User).where(User.email == email)
            result = await session.execute(stmt)
            user = result.scalars().first()
            if not user:
                user = User(
                    email=email,
                    hashed_password=get_password_hash("testpassword"),
                    is_active=True,
                    is_superuser=False
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                
            logger.info(f"Test User ID: {user.id}")

            # ----------------------------------------------------
            # 1. Test Redis Embedding Cache
            # ----------------------------------------------------
            logger.info("--- Testing Redis Embedding Cache ---")
            test_text = "Layer 3 testing embedding caching with Redis"
            text_hash = hashlib.sha256(test_text.encode("utf-8")).hexdigest()
            
            # Clear cache first if exists
            if redis_service.client:
                await redis_service.client.delete(f"embedding:{text_hash}")
                
            # First call: Cache miss, should generate
            emb1 = await embedding_service.get_embedding(test_text)
            assert emb1 is not None
            assert len(emb1) == 1536
            
            # Verify it was cached in Redis
            if redis_service.client:
                cached_val = await redis_service.get_cached_embedding(text_hash)
                assert cached_val is not None
                assert cached_val == emb1
                logger.info("Verified embedding is cached in Redis.")
                
            # Second call: Should hit cache. We temporarily patch generate_embeddings to verify it's not called
            with patch.object(embedding_service.llm, "generate_embeddings", new_callable=AsyncMock) as mock_gen:
                emb2 = await embedding_service.get_embedding(test_text)
                assert emb2 == emb1
                mock_gen.assert_not_called()
                logger.info("Verified second call hits Redis cache and avoids LLM call.")

            # ----------------------------------------------------
            # 2. Test Parsing and OCR Fallback
            # ----------------------------------------------------
            logger.info("--- Testing OCR Fallback Parsing ---")
            # Create a temporary empty file or dummy file path
            dummy_pdf = "C:/Users/aryan/.gemini/antigravity/scratch/ai-exam-platform/backend/storage_uploads/dummy_scanned.pdf"
            
            # Make sure directory exists
            import os
            os.makedirs(os.path.dirname(dummy_pdf), exist_ok=True)
            with open(dummy_pdf, "w") as f:
                f.write("scanned pdf simulation")
                
            # Mock pypdf to return no/very short text
            # Mock pdf2image and pytesseract to simulate OCR
            mock_reader = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "short"  # triggers OCR fallback
            mock_reader.pages = [mock_page]
            
            with patch("pypdf.PdfReader", return_value=mock_reader), \
                 patch("pdf2image.convert_from_path", return_value=[MagicMock()]) as mock_convert, \
                 patch("pytesseract.image_to_string", return_value="This is OCR extracted text.") as mock_ocr:
                 
                parser = PDFParser()
                results = parser.parse(dummy_pdf)
                
                assert len(results) == 1
                assert results[0]["content"] == "This is OCR extracted text."
                assert results[0]["page_number"] == 1
                mock_convert.assert_called_once_with(dummy_pdf)
                mock_ocr.assert_called_once()
                logger.info("Verified OCR fallback parses scanned files and calls pytesseract/pdf2image.")

            # Cleanup dummy pdf
            if os.path.exists(dummy_pdf):
                os.remove(dummy_pdf)

            # ----------------------------------------------------
            # 3. Test Ingestion and Relationship Persistence
            # ----------------------------------------------------
            logger.info("--- Testing Ingestion Flow & Relationships ---")
            dummy_file = "C:/Users/aryan/.gemini/antigravity/scratch/ai-exam-platform/backend/storage_uploads/test_relations.txt"
            slide_one = "This is slide one discussing virtual memory and pagination. Virtual memory paging processes. " * 9
            slide_two = "This is slide two discussing CPU scheduling and threads. Context switching processes. " * 9
            test_content = f"{slide_one}\n\n{slide_two}"
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write(test_content)
                
            sha256_val = hashlib.sha256(test_content.encode("utf-8")).hexdigest()
            
            # Run Ingestion
            doc = await document_ingestion_flow.execute(
                session=session,
                user_id=user.id,
                filename="test_relations.txt",
                storage_path=dummy_file,
                sha256=sha256_val
            )
            
            assert doc is not None
            assert doc.sha256 == sha256_val
            logger.info(f"Ingested document ID: {doc.id}")
            
            # Verify chunks created
            stmt_ch = select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            result_ch = await session.execute(stmt_ch)
            chunks = result_ch.scalars().all()
            assert len(chunks) == 2
            logger.info(f"Found {len(chunks)} chunks in DB with offsets: "
                        f"char_start={chunks[0].char_start}, char_end={chunks[0].char_end}")
            
            # Verify relations persisted
            stmt_rel = select(DocumentChunkRelationship)
            result_rel = await session.execute(stmt_rel)
            rels = result_rel.scalars().all()
            assert len(rels) > 0
            logger.info(f"Verified {len(rels)} relationships successfully committed to DB.")
            
            # Verify metadata extraction fields
            for chunk in chunks:
                meta = chunk.metadata_json
                assert "subject" in meta
                assert "topic" in meta
                assert "chapter" in meta
                assert "academic_domain" in meta
                assert "language" in meta
                assert "estimated_difficulty" in meta
                assert "source_filename" in meta
                assert "page_number" in meta
            logger.info("Verified all citation-aware and academic metadata fields are stored in chunk metadata.")

            # Cleanup dummy file
            if os.path.exists(dummy_file):
                os.remove(dummy_file)

            # ----------------------------------------------------
            # 4. Test Reranking & Telemetry
            # ----------------------------------------------------
            logger.info("--- Testing Reranking & Telemetry ---")
            
            with patch.object(analytics_tracker, "track_pipeline_latency") as mock_track, \
                 patch.object(retrieval_service, "_score_chunk_relevance", side_effect=[9.5, 3.2]):
                 
                # Retrieve context for query
                query = "virtual memory paging"
                context = await retrieval_service.retrieve_context(
                    session=session,
                    query=query,
                    document_id=doc.id,
                    limit=2
                )
                
                # Verify context was retrieved and formatted
                assert context != ""
                logger.info("Retrieved contextual text:\n" + context)
                
                # Verify telemetry was called
                mock_track.assert_called_once()
                args, kwargs = mock_track.call_args
                assert args[0] == "retrieval_service"
                meta = args[2]
                assert "query_length" in meta
                assert "embedding_latency" in meta
                assert "rerank_scores" in meta
                assert len(meta["rerank_scores"]) > 0
                assert meta["failed_retrieval"] is False
                logger.info(f"Verified telemetry logs retrieval analytics: {meta}")

            logger.success("All Layer 3 Integration Tests completed successfully!")
    finally:
        await redis_service.disconnect()

if __name__ == "__main__":
    asyncio.run(run_tests())
