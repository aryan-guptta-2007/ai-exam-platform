import uuid
from typing import List, Dict, Tuple, Any, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import DocumentChunk
from loguru import logger

async def search_chunks_vector(
    session: AsyncSession, 
    query_vector: List[float], 
    document_id: Optional[uuid.UUID] = None,
    limit: int = 5
) -> List[Tuple[DocumentChunk, float]]:
    """
    Executes a vector similarity search using Cosine Distance.
    Returns a list of tuples containing (DocumentChunk, score).
    Score is calculated as (1 - distance) which represents similarity.
    """
    try:
        # Distance calculation
        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        stmt = select(DocumentChunk, (1.0 - distance).label("similarity"))
        
        # Apply filters
        if document_id:
            stmt = stmt.where(DocumentChunk.document_id == document_id)
            
        stmt = stmt.order_by(distance.asc()).limit(limit)
        
        result = await session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]
    except Exception as e:
        logger.error(f"Vector search query failed: {e}")
        return []

async def search_chunks_keyword(
    session: AsyncSession,
    query_text: str,
    document_id: Optional[uuid.UUID] = None,
    limit: int = 5
) -> List[DocumentChunk]:
    """
    Executes a simple keyword search against the document chunk content.
    For production, this could be upgraded to PostgreSQL full-text search (tsvector).
    """
    try:
        stmt = select(DocumentChunk)
        
        # Split search terms for basic AND matching
        words = query_text.split()
        filters = []
        for word in words:
            filters.append(DocumentChunk.content.ilike(f"%{word}%"))
            
        if filters:
            stmt = stmt.where(and_(*filters))
            
        if document_id:
            stmt = stmt.where(DocumentChunk.document_id == document_id)
            
        stmt = stmt.limit(limit)
        
        result = await session.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Keyword search query failed: {e}")
        return []

async def search_chunks_hybrid(
    session: AsyncSession,
    query_text: str,
    query_vector: List[float],
    document_id: Optional[uuid.UUID] = None,
    limit: int = 5,
    rrf_k: int = 60
) -> List[Tuple[DocumentChunk, float]]:
    """
    Implements Reciprocal Rank Fusion (RRF) combining vector and keyword search scores.
    Formula: RRF_Score = sum( 1 / (k + rank) )
    """
    vector_results = await search_chunks_vector(session, query_vector, document_id, limit=limit*2)
    keyword_results = await search_chunks_keyword(session, query_text, document_id, limit=limit*2)
    
    # Track ranks
    rrf_scores: Dict[uuid.UUID, float] = {}
    chunk_map: Dict[uuid.UUID, DocumentChunk] = {}
    
    # Add vector ranks
    for rank, (chunk, _) in enumerate(vector_results, start=1):
        chunk_map[chunk.id] = chunk
        rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (rrf_k + rank))
        
    # Add keyword ranks
    for rank, chunk in enumerate(keyword_results, start=1):
        chunk_map[chunk.id] = chunk
        rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (rrf_k + rank))
        
    # Sort by RRF score descending
    sorted_scores = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    # Return matched chunks with their scores
    return [(chunk_map[chunk_id], score) for chunk_id, score in sorted_scores]
