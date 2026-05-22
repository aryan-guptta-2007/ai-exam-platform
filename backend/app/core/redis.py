import time
from typing import Optional, List
import redis.asyncio as aioredis
from app.core.config import settings
from loguru import logger

class RedisService:
    def __init__(self):
        self.client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        try:
            self.client = aioredis.from_url(
                settings.REDIS_URL, 
                encoding="utf-8", 
                decode_responses=True
            )
            await self.client.ping()
            logger.info("Connected successfully to Redis client.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis at {settings.REDIS_URL}: {e}")
            raise e

    async def disconnect(self) -> None:
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Redis client.")

    async def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """
        Implements a sliding window rate limiter using Redis sorted sets (zset).
        Returns True if allowed, False if rate limited.
        """
        if not self.client:
            logger.warning("Redis client not initialized, skipping rate limiting checks.")
            return True
            
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # Transaction pipeline to ensure atomicity
        async with self.client.pipeline(transaction=True) as pipe:
            try:
                # Remove requests older than the sliding window
                pipe.zremrangebyscore(key, 0, window_start)
                # Count elements in the window
                pipe.zcard(key)
                # Add the current request time
                pipe.zadd(key, {str(current_time): current_time})
                # Set TTL on the key to prevent memory leak
                pipe.expire(key, window_seconds + 5)
                # Execute pipeline
                _, count, _, _ = await pipe.execute()
                
                if count >= max_requests:
                    logger.warning(f"Rate limit exceeded for key {key}. Requests: {count}/{max_requests}")
                    return False
                return True
            except Exception as e:
                logger.error(f"Error in Redis rate limiter: {e}")
                return True # Fail open to prevent complete outage, or return False if strict

    async def add_to_blacklist(self, token_jti: str, expire_seconds: int) -> None:
        if self.client:
            await self.client.setex(f"blacklist:{token_jti}", expire_seconds, "true")

    async def is_token_blacklisted(self, token_jti: str) -> bool:
        if not self.client:
            return False
        return await self.client.exists(f"blacklist:{token_jti}") > 0

    async def get_cached_embedding(self, sha256_hash: str) -> Optional[List[float]]:
        if not self.client:
            return None
        try:
            cached = await self.client.get(f"embedding:{sha256_hash}")
            if cached:
                import json
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Error reading embedding from Redis cache: {e}")
        return None

    async def set_cached_embedding(self, sha256_hash: str, embedding: List[float], expire_seconds: int = 30 * 24 * 3600) -> None:
        if not self.client:
            return
        try:
            import json
            await self.client.setex(f"embedding:{sha256_hash}", expire_seconds, json.dumps(embedding))
        except Exception as e:
            logger.error(f"Error writing embedding to Redis cache: {e}")

redis_service = RedisService()
