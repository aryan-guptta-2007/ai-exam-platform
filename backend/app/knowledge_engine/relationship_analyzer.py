from typing import Dict, List, Any
import numpy as np
from loguru import logger

class RelationshipAnalyzer:
    """
    Core IP component: Analyzes conceptual links and parent-child hierarchies between document chunks.
    This enables building a graph of topics for RAG context building.
    """
    def __init__(self):
        pass

    def analyze_sequential_relations(self, chunks: List[str]) -> List[Dict[str, Any]]:
        """
        Creates references mapping slide transitions (e.g. Slide 1 -> Slide 2).
        """
        relationships = []
        for i in range(len(chunks) - 1):
            relationships.append({
                "source_index": i,
                "target_index": i + 1,
                "type": "sequence_next",
                "weight": 1.0
            })
        return relationships

    def detect_cross_references(self, chunks: List[str], chunk_embeddings: List[List[float]]) -> List[Dict[str, Any]]:
        """
        Calculates similarity between non-sequential chunks to detect cross-references.
        """
        if len(chunks) < 2 or len(chunk_embeddings) != len(chunks):
            return []
            
        relationships = []
        embed_matrix = np.array(chunk_embeddings)
        
        # Calculate cosine similarity matrix
        norm = np.linalg.norm(embed_matrix, axis=1, keepdims=True)
        normalized_embeds = embed_matrix / np.where(norm == 0, 1, norm)
        similarity_matrix = np.dot(normalized_embeds, normalized_embeds.T)
        
        num_chunks = len(chunks)
        for i in range(num_chunks):
            for j in range(i + 2, num_chunks): # Look ahead beyond sequence next
                sim = float(similarity_matrix[i, j])
                # High similarity indicates conceptual linkage
                if sim > 0.82: 
                    relationships.append({
                        "source_index": i,
                        "target_index": j,
                        "type": "concept_related",
                        "weight": sim
                    })
                    logger.debug(f"Conceptual relationship detected between chunk {i} and {j} (sim: {sim:.2f})")
                    
        return relationships
