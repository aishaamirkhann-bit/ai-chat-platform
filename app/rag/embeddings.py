"""
rag/models.py — Document Storage Table

pgvector extension use karte hain embeddings store karne ke liye
Vector type = float numbers ki list jo text ka meaning represent karti hai
"""

import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    filename   = Column(String(255))
    content    = Column(Text, nullable=False)           # Original text chunk
    embedding  = Column(Text)                           # JSON string (pgvector na ho to)
    chunk_idx  = Column(Integer, default=0)             # Konsa chunk hai (0, 1, 2...)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Document id={self.id} file={self.filename} chunk={self.chunk_idx}>"