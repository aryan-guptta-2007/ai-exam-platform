import uuid
import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ai.embeddings import embedding_service
from app.vector_store.queries import search_chunks_hybrid
from app.feature_flags.client import feature_flags
from app.services.llm import get_llm_provider
from app.analytics.tracker import analytics_tracker
from loguru import logger

class RetrievalService:
    """
    RAG Retrieval Pipeline. Performs vector and keyword lookup,
    RRF combination, semantic reranking via LLM, and context compression.
    Tracks latency, rerank scores, and telemetry metrics.
    """
    def __init__(self):
        self.llm = get_llm_provider()

    async def retrieve_context(
        self, 
        session: AsyncSession, 
        query: str, 
        document_id: Optional[uuid.UUID] = None,
        limit: int = 5
    ) -> str:
        """
        Main interface to retrieve relevant contextual paragraphs.
        """
        start_time = time.time()
        logger.info(f"RAG retrieval requested. Query: '{query}' | Doc filter: {document_id}")
        
        # 1. Compute embedding vector and track embedding duration
        emb_start = time.time()
        query_vector = await embedding_service.get_embedding(query)
        embedding_duration = time.time() - emb_start
        
        # 2. Execute Hybrid Search
        if feature_flags.is_enabled("hybrid_retrieval"):
            matched_chunks = await search_chunks_hybrid(
                session=session,
                query_text=query,
                query_vector=query_vector,
                document_id=document_id,
                limit=limit * 2 # Retrieve more for reranking
            )
        else:
            # Fallback to pure vector search if flag disabled
            from app.vector_store.queries import search_chunks_vector
            vector_res = await search_chunks_vector(session, query_vector, document_id, limit=limit * 2)
            matched_chunks = vector_res
            
        if not matched_chunks:
            logger.warning("RAG retrieval yielded zero chunks.")
            latency = time.time() - start_time
            
            # Telemetry tracking for failed retrieval
            analytics_tracker.track_pipeline_latency(
                "retrieval_service",
                latency,
                {
                    "query_length": len(query),
                    "embedding_latency": embedding_duration,
                    "rerank_scores": [],
                    "failed_retrieval": True,
                    "doc_filter": str(document_id) if document_id else None
                }
            )
            return ""
            
        # 3. Rerank and Compress Context
        compressed_chunks, rerank_scores = await self._rerank_and_compress(query, matched_chunks, limit)
        
        # 4. Join and format
        formatted_context = "\n\n".join([
            f"[Source chunk {idx + 1} | File {chunk.metadata_json.get('source_filename', 'unknown')} | Page {chunk.metadata_json.get('page_number', 'unknown')}]:\n{chunk.content}"
            for idx, chunk in enumerate(compressed_chunks)
        ])
        
        latency = time.time() - start_time
        logger.info(f"Retrieved context size: {len(formatted_context)} characters across {len(compressed_chunks)} chunks.")
        
        # Telemetry tracking
        analytics_tracker.track_pipeline_latency(
            "retrieval_service",
            latency,
            {
                "query_length": len(query),
                "embedding_latency": embedding_duration,
                "rerank_scores": rerank_scores,
                "failed_retrieval": False,
                "doc_filter": str(document_id) if document_id else None
            }
        )
        
        return formatted_context

    async def _score_chunk_relevance(self, query: str, content: str) -> float:
        system_instruction = (
            "You are an expert search evaluator. Grade the relevance of the text content "
            "to the user query. Output ONLY a single floating-point number or integer "
            "between 0.0 (completely irrelevant) and 10.0 (highly relevant, contains the answer). "
            "Do not include any other text."
        )
        prompt = f"User Query: {query}\nText Content:\n{content}"
        try:
            res = await self.llm.generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.1
            )
            # Parse numeric value
            clean_res = "".join(c for c in res.strip() if c.isdigit() or c == '.')
            return float(clean_res)
        except Exception as e:
            logger.warning(f"Error scoring chunk relevance: {e}")
            return 1.0 # fallback default score

    async def _rerank_and_compress(self, query: str, chunks_with_scores: List[Any], limit: int) -> Tuple[List[Any], List[float]]:
        """
        Cleans redundancy, reranks elements using LLM relevance scoring, and compresses context window.
        """
        seen_content = set()
        unique_chunks = []
        
        for item in chunks_with_scores:
            # Handle tuple (chunk, score) or raw chunk
            chunk = item[0] if isinstance(item, tuple) else item
            
            # Simple deduplication
            normalized_content = chunk.content.strip().lower()[:200]
            if normalized_content not in seen_content:
                seen_content.add(normalized_content)
                unique_chunks.append(chunk)
                
        # Score each chunk in parallel
        tasks = [self._score_chunk_relevance(query, c.content) for c in unique_chunks]
        scores = await asyncio.gather(*tasks)
        
        # Pair chunk and score
        paired = list(zip(unique_chunks, scores))
        # Sort descending by score
        paired.sort(key=lambda x: x[1], reverse=True)
        
        selected_chunks = [p[0] for p in paired[:limit]]
        selected_scores = [p[1] for p in paired[:limit]]
        
        return selected_chunks, selected_scores

retrieval_service = RetrievalService()
