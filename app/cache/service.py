import hashlib
import logging

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self):
        self._connected = False

    async def connect(self):
        logger.info("Cache disabled — running without Redis")
        self._connected = False

    async def disconnect(self):
        pass

    def _make_llm_key(self, prompt: str, model: str) -> str:
        content = f"{model}:{prompt.strip().lower()}"
        return f"llm_cache:{hashlib.md5(content.encode()).hexdigest()}"

    async def get_llm_response(self, prompt: str, model: str) -> dict | None:
        return None

    async def set_llm_response(self, prompt: str, model: str, response: dict, ttl_seconds: int = 3600) -> bool:
        return False

    async def check_rate_limit(self, user_id: int, limit: int = 50, window_seconds: int = 3600) -> tuple[bool, int]:
        return True, limit

    async def get_stats(self) -> dict:
        return {"status": "disabled"}


cache_service = CacheService()