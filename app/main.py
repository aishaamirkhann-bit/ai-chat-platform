from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.config import settings
from app.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    print("🚀 Starting AI Chat Platform...")
    await create_tables()
    print(f"📡 API ready at http://localhost:8000/docs")
    yield
    print("👋 Shutting down...")


app = FastAPI(
    title="AI Chat Platform",
    description="""
## AI Chat Platform API

Complete features:
- **JWT Authentication** — Register, Login, Protected routes
- **AI Chat** — OpenAI GPT-4 + Anthropic Claude integration
- **Streaming** — Real-time SSE streaming responses
- **RAG** — Document upload + semantic search
- **Caching** — Redis caching for LLM responses
- **Rate Limiting** — 50 requests per hour per user
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — Allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.rag.router  import router as rag_router

app.include_router(auth_router, prefix="/auth",  tags=["Authentication"])
app.include_router(chat_router, prefix="/chat",  tags=["Chat"])
app.include_router(rag_router,  prefix="/rag",   tags=["RAG / Documents"])


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "features": ["jwt-auth", "streaming", "rag", "caching"]
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "AI Chat Platform API",
        "docs": "/docs",
        "health": "/health"
    }