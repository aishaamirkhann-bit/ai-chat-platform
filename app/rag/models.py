import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    filename   = Column(String(255))
    content    = Column(Text, nullable=False)
    embedding  = Column(Text)
    chunk_idx  = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # back_populates must match User.documents
    user = relationship("User", back_populates="documents")

    def __repr__(self):
        return f"<Document id={self.id} file={self.filename}>"