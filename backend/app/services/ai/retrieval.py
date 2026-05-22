import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ai.embeddings import embedding_service
from app.vector_store.queries import search_chunks_hybrid
from app.feature_flags.client import feature_flags
from loguru import logger

class RetrievalService:
    """
    RAG Retrieval Pipeline. Performs vector and keyword lookup,
    RRF combination, semantic reranking, and context compression.
    """
    def __init__(self):
        pass

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
        logger.info(f"RAG retrieval requested. Query: '{query}' | Doc filter: {document_id}")
        
        # 1. Compute embedding vector
        query_vector = await embedding_service.get_embedding(query)
        
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
            return ""
            
        # 3. Rerank and Compress Context
        compressed_chunks = self._rerank_and_compress(matched_chunks, limit)
        
        # 4. Join and format
        formatted_context = "\n\n".join([
            f"[Source chunk {idx + 1} | Page {chunk.metadata_json.get('page_number', 'unknown')}]:\n{chunk.content}"
            for idx, chunk in enumerate(compressed_chunks)
        ])
        
        logger.info(f"Retrieved context size: {len(formatted_context)} characters across {len(compressed_chunks)} chunks.")
        return formatted_context

    def _rerank_and_compress(self, chunks_with_scores: List[Any], limit: int) -> List[Any]:
        """
        Cleans redundancy, reranks elements, and compresses context window.
        """
        # In a fully-scaled system, this utilizes a cross-encoder model.
        # Here we perform basic similarity ordering and redundant phrase pruning.
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
                
        # Limit to the requested size
        return unique_chunks[:limit]

retrieval_service = RetrievalService()
