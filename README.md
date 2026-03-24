# 💬 NeuralChat — AI Chat Platform

> Real-time AI chat with RAG pipeline, SSE streaming, and JWT auth.

**NeuralChat** is a production-ready AI chat platform built with **FastAPI**, **Google Gemini 2.0 Flash**, and **ChromaDB**. Upload documents and chat with your own data using semantic vector search — with real-time streaming responses.

🔗 **Live:** https://ai-chat-platform-production-1f81.up.railway.app

---

## ✨ Features

- 💬 **Real-time SSE Streaming** — ChatGPT-style token-by-token responses
- 📄 **RAG Pipeline** — Upload documents, query via semantic vector search (ChromaDB)
- 🔐 **JWT Authentication** — Secure register/login with bcrypt hashing
- ⚡ **Rate Limiting** — 50 requests/hour per user
- 🗄️ **Persistent Chat History** — PostgreSQL + async SQLAlchemy ORM
- 🚀 **Deployed on Railway** — Production-ready with Nixpacks

---

## 🏗️ Architecture
```
Frontend (HTML/CSS/JS)
        ↓
   FastAPI Backend
        ↓
┌──────────────────────────────┐
│  Auth  │  Chat  │  RAG       │
│  JWT   │  SSE   │  ChromaDB  │
└──────────────────────────────┘
        ↓           ↓
   PostgreSQL    Gemini 2.0
   (Chat DB)    (LLM Engine)
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.11, Async SQLAlchemy |
| AI Core | Google Gemini 2.0 Flash |
| RAG | ChromaDB, SentenceTransformers |
| Database | PostgreSQL / SQLite |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Streaming | Server-Sent Events (SSE) |
| Deployment | Railway (Nixpacks) |

---

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/aishaamirkhann-bit/ai-chat-platform.git
cd ai-chat-platform
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create `.env`:
```env
DATABASE_URL=sqlite+aiosqlite:///./aichat.db
JWT_SECRET=your-secret-key-here
GEMINI_API_KEY=your-gemini-api-key
```

### 4. Run Backend
```bash
uvicorn app.main:app --reload
```

API running at: http://localhost:8000/docs

---

## 📡 API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | No | Register new user |
| POST | `/auth/login` | No | Login + get JWT token |
| GET | `/chat/conversations` | Yes | List conversations |
| POST | `/chat/conversations` | Yes | Create conversation |
| POST | `/chat/conversations/{id}/stream` | Yes | SSE streaming chat |
| POST | `/rag/upload` | Yes | Upload document |
| GET | `/rag/docs` | Yes | List uploaded docs |

---

## 👩‍💻 Author

**Aisha Amir** — AI Backend Engineer

Building production AI systems with FastAPI, LangGraph, and scalable async architectures.

📧 aishaamirkhann@gmail.com
🌍 Lahore, Pakistan — Open to Remote Opportunities
🔗 GitHub: [aishaamirkhann-bit](https://github.com/aishaamirkhann-bit)

