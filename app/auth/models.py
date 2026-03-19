import datetime
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    name            = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at      = Column(DateTime, default=datetime.datetime.utcnow)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    documents     = relationship("Document",     back_populates="user", cascade="all, delete-orphan")