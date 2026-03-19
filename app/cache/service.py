import hashlib
import json
import logging

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self):
        self.redis: aioredis.Redis | None = None
        self._connected = False

    async def connect(self):
        try:
            self.redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis.ping()
            self._connected = True
            logger.info(" Redis connected!")
        except Exception as e:
            logger.warning(f"⚠️  Redis connect nahi hua: {e} — Caching disabled")
            self._connected = False

    async def disconnect(self):
        if self.redis:
            await self.redis.close()

    #  Key Generation 
    def _make_llm_key(self, prompt: str, model: str) -> str:
    
        content = f"{model}:{prompt.strip().lower()}"
        hash_   = hashlib.md5(content.encode()).hexdigest()
        return f"llm_cache:{hash_}"

    def _make_user_key(self, user_id: int) -> str:
        return f"user:{user_id}"

    #  LLM Cache 
    async def get_llm_response(self, prompt: str, model: str) -> dict | None:
        if not self._connected:
            return None

        try:
            key    = self._make_llm_key(prompt, model)
            cached = await self.redis.get(key)

            if cached:
                logger.info(f"Cache HIT: {key[:30]}...")
                return json.loads(cached)

            logger.info(f"Cache MISS: {key[:30]}...")
            return None

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set_llm_response(
        self,
        prompt: str,
        model: str,
        response: dict,
        ttl_seconds: int = 3600,  # 1 ghanta
    ) -> bool:
        if not self._connected:
            return False

        try:
            key = self._make_llm_key(prompt, model)
            await self.redis.setex(
                key,
                ttl_seconds,
                json.dumps(response),
            )
            logger.info(f"Cached response for {ttl_seconds}s: {key[:30]}...")
            return True

        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    #  Rate Limiting 
    async def check_rate_limit(
        self,
        user_id: int,
        limit: int = 50,
        window_seconds: int = 3600,
    ) -> tuple[bool, int]:
        if not self._connected:
            return True, limit 

        try:
            key   = f"rate_limit:{user_id}"
            count = await self.redis.incr(key)

            if count == 1:
                await self.redis.expire(key, window_seconds)

            remaining = max(0, limit - count)
            allowed   = count <= limit
            return allowed, remaining

        except Exception as e:
            logger.error(f"Rate limit error: {e}")
            return True, limit  

    #  Cache Stats
    async def get_stats(self) -> dict:
        """Cache statistics — monitoring ke liye"""
        if not self._connected:
            return {"status": "disconnected"}

        try:
            info = await self.redis.info("stats")
            return {
                "status": "connected",
                "hits":   info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
            }
        except Exception:
            return {"status": "error"}


#  Singleton 
cache_service = CacheService()