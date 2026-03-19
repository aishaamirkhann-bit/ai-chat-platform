from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App 
    APP_NAME: str = "AI Chat Platform"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    #  Database 
    DATABASE_URL: str

    # Redis 
    REDIS_URL: str = "redis://localhost:6379"

    # JWT 
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # LLM
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str

    @property
    def origins_list(self) -> list[str]:
        """ALLOWED_ORIGINS string ko list mein convert karta hai"""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


# lru_cache — settings ek baar load ho, baar baar nahi
# Dependency injection mein use hoga
@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Global settings object
settings = get_settings()