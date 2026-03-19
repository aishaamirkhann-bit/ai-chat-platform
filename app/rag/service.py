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
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info(" Embedding model loaded!")
    return _embedder


class RAGService:

    #  Text Processing 
    def chunk_text(
        self,
        text: str,  # noqa: F811
        chunk_size: int = 400,
        overlap: int = 50,
    ) -> list[str]:
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
        embedder  = get_embedder()
        embedding = embedder.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    # Cosine Similarity (Manual — pgvector na ho to) 
    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1  = math.sqrt(sum(a * a for a in vec1))
        magnitude2  = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)

    #  Document Indexing 
    async def index_document(
        self,
        content: str,
        filename: str,
        user_id: int,
        db: AsyncSession,
    ) -> int:
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
        logger.info(f" Indexed {len(chunks)} chunks for '{filename}'")
        return len(chunks)

    #  Document Search 
    async def search_documents(
        self,
        query: str,
        user_id: int,
        db: AsyncSession,
        top_k: int = 3,
        min_similarity: float = 0.3,
    ) -> list[dict]:
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

    # Stats 
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


#  Singleton 
rag_service = RAGService()