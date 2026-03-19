"""
rag/service.py — Complete RAG Pipeline

RAG = Retrieval Augmented Generation

Poora flow:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INDEXING (document upload par ek baar):
Document (PDF/TXT)
       ↓
Text extract karo
       ↓
Chunks mein todo (500 words each)
       ↓
Har chunk ko embedding banao (text → 384 numbers)
       ↓
DB mein store karo (content + embedding)

RETRIEVAL (har query par):
User ka sawal
       ↓
Sawal ko bhi embedding banao
       ↓
DB mein cosine similarity se compare karo
       ↓
Top 3 similar chunks nikalo
       ↓
LLM ko context ke sath do
       ↓
LLM apke data se jawab deta hai!

Cosine Similarity kya hai?
Do vectors ke darmiyan angle measure karna
Angle 0° = same meaning = similarity 1.0
Angle 90° = alag meaning = similarity 0.0
"""

import json
import logging
import math

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.models import Document

logger = logging.getLogger(__name__)

# Lazy import — sentence_transformers bhari library hai
_embedder = None


def get_embedder():
    """Embedder ko lazily load karo — app startup slow na ho"""
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("✅ Embedding model loaded!")
    return _embedder


class RAGService:

    # ── Text Processing ───────────────────────────────────────────────────────
    def chunk_text(
        self,
        text: str,
        chunk_size: int = 400,
        overlap: int = 50,
    ) -> list[str]:
        """
        Text ko overlapping chunks mein todo

        Overlap kyun?
        Agar meaning chunk boundary par hai to context na toote
        Chunk 1: "... machine learning models are trained using"
        Chunk 2: "trained using large datasets which contain..."
        Overlap se dono chunks mein "trained using" hai → context safe

        chunk_size=400: 400 words per chunk
        overlap=50:     Last 50 words agle chunk mein bhi
        """
        words  = text.split()
        chunks = []
        start  = 0

        while start < len(words):
            end   = start + chunk_size
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            start += chunk_size - overlap  # Overlap ke saath aage badho

        return chunks

    def embed_text(self, text: str) -> list[float]:
        """
        Text → Embedding Vector
        "Hello world" → [0.12, -0.34, 0.89, ...] (384 numbers)

        Yeh numbers text ka 'meaning' represent karte hain
        Similar meaning → similar numbers
        """
        embedder  = get_embedder()
        embedding = embedder.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    # ── Cosine Similarity (Manual — pgvector na ho to) ────────────────────────
    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Do vectors ke darmiyan similarity calculate karo
        Return: 0.0 (bilkul alag) to 1.0 (same)

        Formula:
        similarity = (A · B) / (|A| × |B|)
        dot product / (magnitude A × magnitude B)
        """
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1  = math.sqrt(sum(a * a for a in vec1))
        magnitude2  = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)

    # ── Document Indexing ─────────────────────────────────────────────────────
    async def index_document(
        self,
        content: str,
        filename: str,
        user_id: int,
        db: AsyncSession,
    ) -> int:
        """
        Document ko process karke DB mein store karo
        Returns: kitne chunks bane
        """
        # Step 1: Chunks banao
        chunks = self.chunk_text(content)
        logger.info(f"Document '{filename}' → {len(chunks)} chunks")

        # Step 2: Har chunk ko embed karo aur save karo
        for i, chunk in enumerate(chunks):
            embedding = self.embed_text(chunk)

            doc = Document(
                user_id=user_id,
                filename=filename,
                content=chunk,
                embedding=json.dumps(embedding),  # JSON string mein store
                chunk_idx=i,
            )
            db.add(doc)

        await db.commit()
        logger.info(f"✅ Indexed {len(chunks)} chunks for '{filename}'")
        return len(chunks)

    # ── Document Search ───────────────────────────────────────────────────────
    async def search_documents(
        self,
        query: str,
        user_id: int,
        db: AsyncSession,
        top_k: int = 3,
        min_similarity: float = 0.3,
    ) -> list[dict]:
        """
        Query se similar documents dhundho

        Steps:
        1. Query ko embed karo
        2. Is user ke saare documents lo
        3. Har document se similarity calculate karo
        4. Top K results return karo

        Production mein:
        pgvector use karo → SQL level par vector search
        SELECT * FROM documents
        ORDER BY embedding <=> query_vector  ← pgvector operator
        LIMIT 3

        Yahan hum Python mein kar rahe hain (simplicity ke liye)
        """
        # Query embed karo
        query_embedding = self.embed_text(query)

        # Is user ke saare documents lo
        result = await db.execute(
            select(Document).where(Document.user_id == user_id)
        )
        documents = result.scalars().all()

        if not documents:
            logger.info("Koi documents nahi milse")
            return []

        # Similarity calculate karo
        scored_docs = []
        for doc in documents:
            if not doc.embedding:
                continue

            doc_embedding = json.loads(doc.embedding)
            similarity    = self.cosine_similarity(query_embedding, doc_embedding)

            if similarity >= min_similarity:
                scored_docs.append({
                    "content":    doc.content,
                    "filename":   doc.filename,
                    "chunk_idx":  doc.chunk_idx,
                    "similarity": round(similarity, 4),
                })

        # Similarity ke hisaab se sort karo (highest first)
        scored_docs.sort(key=lambda x: x["similarity"], reverse=True)

        top_results = scored_docs[:top_k]
        logger.info(f"Query: '{query[:50]}...' → {len(top_results)} results mili")
        return top_results

    # ── Stats ─────────────────────────────────────────────────────────────────
    async def get_user_documents(self, user_id: int, db: AsyncSession) -> list[dict]:
        """User ke indexed documents ki list"""
        result = await db.execute(
            select(Document.filename, Document.chunk_idx, Document.created_at)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
        )
        rows = result.fetchall()
        seen = set()
        files = []
        for row in rows:
            if row.filename not in seen:
                seen.add(row.filename)
                files.append({
                    "filename":   row.filename,
                    "created_at": str(row.created_at),
                })
        return files


# ─── Singleton ────────────────────────────────────────────────────────────────
rag_service = RAGService()