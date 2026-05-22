import uuid
from typing import Dict, Any, List, Tuple
from app.knowledge_engine.chunker import DocumentChunker
from app.knowledge_engine.metadata_extractor import MetadataExtractor
from app.knowledge_engine.relationship_analyzer import RelationshipAnalyzer
from app.utils.parsers.factory import ParserFactory
from app.services.ai.embeddings import embedding_service
from loguru import logger

class DocumentIndexer:
    def __init__(self):
        self.chunker = DocumentChunker()
        self.metadata_extractor = MetadataExtractor()
        self.relationship_analyzer = RelationshipAnalyzer()

    async def index_document(
        self, 
        file_path: str, 
        filename: str
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Coordinates document indexing:
        1. Parses document page-by-page.
        2. Splits text pages into chunks.
        3. Generates embedding vectors utilizing embedding_service (Redis caching).
        4. Analyzes semantic and sequential relationships.
        5. Extracts summary metadata.
        
        Returns:
            metadata: Dict[str, Any]
            chunks: List[Dict[str, Any]] (containing content, embeddings, and chunk metadata)
            relationships: List[Dict[str, Any]]
        """
        logger.info(f"Starting indexing pipeline for document: {filename} from path: {file_path}")
        
        # 1. Parsing
        parser = ParserFactory.get_parser(file_path)
        parsed_pages = parser.parse(file_path)
        logger.info(f"Parsed document into {len(parsed_pages)} pages.")
        
        # Reconstruct full text for metadata extraction
        full_text = "\n\n".join([page["content"] for page in parsed_pages])
        
        # 2. Chunking
        chunks = self.chunker.chunk_document(parsed_pages)
        logger.info(f"Split document into {len(chunks)} chunks.")
        
        # 3. Extract Overall Metadata
        doc_metadata = await self.metadata_extractor.extract_metadata(full_text, filename)
        
        # 4. Generate Embeddings using embedding_service (Redis caching & telemetry)
        logger.info("Generating embedding vectors for chunks...")
        chunk_texts = [c["content"] for c in chunks]
        embeddings = await embedding_service.get_embeddings(chunk_texts)
        
        # Pack chunks with embeddings and metadata
        chunks_payload = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunks_payload.append({
                "index": idx,
                "content": chunk["content"],
                "embedding": embedding,
                "metadata": {
                    "page_number": chunk["page_number"],
                    "char_start": chunk["char_start"],
                    "char_end": chunk["char_end"],
                    "paragraph_references": chunk["paragraph_references"],
                    "length": len(chunk["content"]),
                    "source_filename": filename
                }
            })
            
        # 5. Analyze Relationships
        seq_relations = self.relationship_analyzer.analyze_sequential_relations(chunk_texts)
        cross_relations = self.relationship_analyzer.detect_cross_references(chunk_texts, embeddings)
        
        all_relationships = seq_relations + cross_relations
        logger.info(f"Index pipeline complete. Found {len(all_relationships)} chunk relationships.")
        
        return doc_metadata, chunks_payload, all_relationships

indexer = DocumentIndexer()
