from typing import List, Union
from app.services.llm import get_llm_provider
from loguru import logger

class EmbeddingService:
    def __init__(self):
        self.llm = get_llm_provider()

    async def get_embedding(self, text: str) -> List[float]:
        """
        Gets embedding vector for a single text input.
        """
        try:
            vectors = await self.llm.generate_embeddings(text)
            return vectors[0]
        except Exception as e:
            logger.error(f"Failed to generate embedding for text: {e}")
            raise e

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Gets embeddings for a batch of text inputs.
        """
        try:
            return await self.llm.generate_embeddings(texts)
        except Exception as e:
            logger.error(f"Failed to generate embeddings for batch: {e}")
            raise e

embedding_service = EmbeddingService()
