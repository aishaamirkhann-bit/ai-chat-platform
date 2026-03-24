NeuralChat — AI Chat Platform
A production-ready AI backend with real-time streaming, RAG pipeline, and JWT authentication — built with FastAPI and Google Gemini.

🔗 GitHub: aishaamirkhann-bit/ai-chat-platform

Features
JWT Authentication — Secure register, login, and protected routes with bcrypt
Gemini AI Chat — Real-time conversations powered by Google Gemini 2.0 Flash
Streaming Responses — Server-Sent Events (SSE) for ChatGPT-like UX
RAG Pipeline — Upload documents, ask questions about your own data
Persistent History — Full conversation history saved per user session
Rate Limiting — 50 requests/hour per user
Async Architecture — Handles concurrent users efficiently with async SQLAlchemy
Screenshots
Chat UI
NeuralChat UI

API Docs (Swagger)
Swagger

Architecture
Client (Browser)
      ↓
FastAPI Backend
      ↓
┌──────────────────────────────────┐
│  Auth (JWT)  │  Chat  │  RAG     │
│  bcrypt      │ Gemini │ Embeddings│
└──────────────────────────────────┘
      ↓              ↓          ↓
  SQLite/PG      Gemini API   Vector Search
 (Users, Chats)  (Streaming)  (SentenceTransformers)
Request Flow:

User sends message → JWT verified
If RAG enabled → relevant document chunks retrieved
Gemini called with context + history → response streamed back via SSE
Message saved to database with full history
Tech Stack
Layer	Technology
Backend	Python, FastAPI, Async SQLAlchemy
AI Model	Google Gemini 2.0 Flash
Database	SQLite (dev) / PostgreSQL (prod)
Embeddings	SentenceTransformers
Auth	JWT (python-jose, bcrypt)
Streaming	Server-Sent Events (SSE)
Quick Start
# Clone
git clone https://github.com/aishaamirkhann-bit/ai-chat-platform.git
cd ai-chat-platform

# Virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Mac/Linux

# Install
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Add your GEMINI_API_KEY in .env

# Run
uvicorn app.main:app --reload

# Open
# http://localhost:8000/docs
Environment Variables
DATABASE_URL=sqlite+aiosqlite:///./aichat.db
SECRET_KEY=your-secret-key-here
GEMINI_API_KEY=your-gemini-api-key-here
Get a free Gemini API key at: https://aistudio.google.com/app/apikey

API Endpoints
Method	Endpoint	Auth	Description
POST	/auth/register	No	Register new user
POST	/auth/login	No	Login + get JWT token
GET	/auth/me	Yes	Get current user info
POST	/chat/conversations	Yes	Create conversation
GET	/chat/conversations	Yes	List all conversations
POST	/chat/conversations/{id}	Yes	Send message (non-streaming)
POST	/chat/conversations/{id}/stream	Yes	Streaming chat (SSE)
POST	/rag/upload	Yes	Upload document for RAG
GET	/rag/docs	Yes	List uploaded documents
GET	/health	No	Health check
Key Technical Decisions
Why FastAPI? Built for async workloads. LLM calls take 2-5 seconds — async allows handling hundreds of concurrent requests without blocking.

Why Gemini over OpenAI? Google Gemini offers a generous free tier with no credit card required, making it ideal for development and portfolio projects. The API is production-ready and supports streaming.

Why RAG over Fine-tuning? RAG allows real-time document updates without retraining. More flexible and cost-effective for private/custom data.

Why JWT over Sessions? Stateless — the server stores nothing. Horizontally scalable across multiple servers for cloud deployments.

Project Structure
app/
├── main.py              ← FastAPI app entry point
├── config.py            ← Environment settings
├── database.py          ← Async SQLAlchemy setup
├── auth/
│   ├── models.py        ← User table
│   ├── service.py       ← JWT + bcrypt logic
│   └── router.py        ← Auth endpoints
├── chat/
│   ├── models.py        ← Conversation + Message tables
│   ├── service.py       ← Gemini AI integration
│   └── router.py        ← Chat + streaming endpoints
├── rag/
│   ├── models.py        ← Document table
│   ├── service.py       ← Embeddings + vector search
│   └── router.py        ← Upload + search endpoints
└── cache/
    └── service.py       ← Rate limiting
Use Cases
AI chatbot for businesses
Document Q&A systems (internal knowledge base)
Customer support automation
Research assistant with private data
Author
Aisha Amir — AI Backend Engineer

Backend Engineer specializing in AI systems — FastAPI, RAG pipelines, LLM integration, and scalable async architectures.

📧 aishaamirkhann@gmail.com
🌍 Lahore, Pakistan — Open to Remote & Relocation
