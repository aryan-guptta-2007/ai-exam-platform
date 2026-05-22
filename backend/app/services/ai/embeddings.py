import hashlib
import time
from typing import List, Optional
from app.services.llm import get_llm_provider
from app.core.redis import redis_service
from app.analytics.tracker import analytics_tracker
from loguru import logger

class EmbeddingService:
    def __init__(self):
        self.llm = get_llm_provider()

    def _get_text_sha256(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def get_embedding(self, text: str) -> List[float]:
        """
        Gets embedding vector for a single text input, utilizing Redis caching.
        """
        sha256_hash = self._get_text_sha256(text)
        
        # Check cache
        try:
            cached = await redis_service.get_cached_embedding(sha256_hash)
            if cached is not None:
                logger.debug(f"Embedding cache hit for hash: {sha256_hash}")
                return cached
        except Exception as e:
            logger.warning(f"Error checking embedding cache: {e}")

        # Cache miss, generate embedding and time it
        start_time = time.time()
        try:
            vectors = await self.llm.generate_embeddings(text)
            embedding = vectors[0]
            duration = time.time() - start_time
            
            # Telemetry tracking
            analytics_tracker.track_llm_call(
                model_name=getattr(self.llm, "embedding_model", "embedding-model"),
                duration_seconds=duration,
                success=True
            )
            
            # Cache the result
            try:
                await redis_service.set_cached_embedding(sha256_hash, embedding)
            except Exception as e:
                logger.warning(f"Failed to cache embedding in Redis: {e}")
                
            return embedding
        except Exception as e:
            duration = time.time() - start_time
            analytics_tracker.track_llm_call(
                model_name=getattr(self.llm, "embedding_model", "embedding-model"),
                duration_seconds=duration,
                success=False,
                error=str(e)
            )
            logger.error(f"Failed to generate embedding for text: {e}")
            raise e

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Gets embeddings for a batch of text inputs, utilizing Redis caching and batch generation.
        """
        if not texts:
            return []

        # 1. Compute hashes for all texts
        hashes = [self._get_text_sha256(text) for text in texts]
        
        # 2. Check cache for all texts
        cached_results = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []
        
        for idx, sha256_hash in enumerate(hashes):
            try:
                cached = await redis_service.get_cached_embedding(sha256_hash)
                if cached is not None:
                    cached_results[idx] = cached
                else:
                    uncached_indices.append(idx)
                    uncached_texts.append(texts[idx])
            except Exception as e:
                logger.warning(f"Error checking cache for index {idx}: {e}")
                uncached_indices.append(idx)
                uncached_texts.append(texts[idx])

        # 3. If there are uncached texts, generate embeddings
        if uncached_texts:
            start_time = time.time()
            try:
                logger.info(f"Generating embeddings for {len(uncached_texts)} uncached texts")
                generated_embeddings = await self.llm.generate_embeddings(uncached_texts)
                duration = time.time() - start_time
                
                # Telemetry tracking
                analytics_tracker.track_llm_call(
                    model_name=getattr(self.llm, "embedding_model", "embedding-model"),
                    duration_seconds=duration,
                    success=True
                )
                
                # Update cached_results and cache in Redis
                for gen_idx, orig_idx in enumerate(uncached_indices):
                    emb = generated_embeddings[gen_idx]
                    cached_results[orig_idx] = emb
                    try:
                        await redis_service.set_cached_embedding(hashes[orig_idx], emb)
                    except Exception as e:
                        logger.warning(f"Failed to cache embedding for hash {hashes[orig_idx]}: {e}")
                        
            except Exception as e:
                duration = time.time() - start_time
                analytics_tracker.track_llm_call(
                    model_name=getattr(self.llm, "embedding_model", "embedding-model"),
                    duration_seconds=duration,
                    success=False,
                    error=str(e)
                )
                logger.error(f"Failed to generate embeddings for batch: {e}")
                raise e

        return cached_results

embedding_service = EmbeddingService()
