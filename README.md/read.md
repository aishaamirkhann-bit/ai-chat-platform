# 🤖 AI Chat Platform

Production-ready AI backend built with FastAPI, PostgreSQL, Redis, and OpenAI.

## ✨ Features

- **JWT Authentication** — Register, Login, Protected routes
- **AI Chat** — OpenAI GPT-4 + Anthropic Claude integration  
- **Streaming** — Real-time SSE streaming (ChatGPT-like experience)
- **RAG Pipeline** — Upload documents, ask questions about your data
- **Redis Caching** — 60-70% LLM cost reduction
- **Rate Limiting** — 50 requests/hour per user

## 🛠️ Tech Stack

- **Backend:** Python, FastAPI, Async SQLAlchemy
- **Database:** PostgreSQL
- **Cache:** Redis
- **AI:** OpenAI GPT-4, Anthropic Claude, SentenceTransformers
- **Auth:** JWT (python-jose, bcrypt)
- **Deploy:** AWS (EC2, RDS, ElastiCache)

## 🚀 Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Add your API keys in .env

# Run
uvicorn app.main:app --reload
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /auth/register | Register new user |
| POST | /auth/login | Login + get JWT token |
| POST | /chat/conversations | Create conversation |
| POST | /chat/conversations/{id}/stream | Streaming chat |
| POST | /rag/upload | Upload document for RAG |
| GET  | /health | Health check |

## 📸 Demo

Live API docs: `http://localhost:8000/docs`