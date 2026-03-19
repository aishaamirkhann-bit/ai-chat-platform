import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title      = Column(String(200), default="New Conversation")
    model_used = Column(String(50), default="gpt-4o-mini")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    # Relationships
    user     = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",  # Hamesha chronological order
    )

    def __repr__(self):
        return f"<Conversation id={self.id} title={self.title}>"


class Message(Base):
    __tablename__ = "messages"

    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    role            = Column(String(20), nullable=False)  # 'user' ya 'assistant'
    content         = Column(Text, nullable=False)
    tokens_used     = Column(Integer, default=0)
    model_used      = Column(String(50))
    created_at      = Column(DateTime, default=datetime.datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message id={self.id} role={self.role}>"