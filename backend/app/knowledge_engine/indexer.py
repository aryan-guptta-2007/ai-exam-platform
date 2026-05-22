import uuid
from typing import Dict, Any, List, Tuple
from app.knowledge_engine.chunker import DocumentChunker
from app.knowledge_engine.metadata_extractor import MetadataExtractor
from app.knowledge_engine.relationship_analyzer import RelationshipAnalyzer
from app.services.llm import get_llm_provider
from loguru import logger

class DocumentIndexer:
    def __init__(self):
        self.chunker = DocumentChunker()
        self.metadata_extractor = MetadataExtractor()
        self.relationship_analyzer = RelationshipAnalyzer()
        self.llm = get_llm_provider()

    async def index_document(
        self, 
        document_text: str, 
        filename: str
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Coordinates document indexing:
        1. Splits text into chunks.
        2. Generates embedding vectors for each chunk.
        3. Analyzes semantic and sequential relationships.
        4. Extracts summary metadata.
        
        Returns:
            metadata: Dict[str, Any]
            chunks: List[Dict[str, Any]] (containing content, embeddings, and chunk metadata)
            relationships: List[Dict[str, Any]]
        """
        logger.info(f"Starting indexing pipeline for document: {filename}")
        
        # 1. Chunking
        raw_chunks = self.chunker.split_text(document_text)
        logger.info(f"Split document into {len(raw_chunks)} chunks.")
        
        # 2. Extract Overall Metadata
        doc_metadata = await self.metadata_extractor.extract_metadata(document_text, filename)
        
        # 3. Generate Embeddings
        logger.info("Generating embedding vectors for chunks...")
        embeddings = await self.llm.generate_embeddings(raw_chunks)
        
        # Pack chunks with embeddings and index-level metadata
        chunks_payload = []
        for idx, (content, embedding) in enumerate(zip(raw_chunks, embeddings)):
            chunks_payload.append({
                "index": idx,
                "content": content,
                "embedding": embedding,
                "metadata": {
                    "page_number": idx + 1,
                    "length": len(content)
                }
            })
            
        # 4. Analyze Relationships
        seq_relations = self.relationship_analyzer.analyze_sequential_relations(raw_chunks)
        cross_relations = self.relationship_analyzer.detect_cross_references(raw_chunks, embeddings)
        
        all_relationships = seq_relations + cross_relations
        logger.info(f"Index pipeline complete. Found {len(all_relationships)} chunk relationships.")
        
        return doc_metadata, chunks_payload, all_relationships
        
indexer = DocumentIndexer()
