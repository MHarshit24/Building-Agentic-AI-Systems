from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class QueryModel(Base):
    """
    SQLAlchemy model for storing user queries and AI responses.
    """

    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, index=True)
    concept = Column(String, nullable=False)
    explanation = Column(Text, nullable=False)
    model = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)