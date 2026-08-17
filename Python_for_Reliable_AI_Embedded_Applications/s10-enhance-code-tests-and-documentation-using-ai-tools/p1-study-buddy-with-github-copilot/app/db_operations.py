import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .query_model import Base, QueryModel

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create tables automatically
Base.metadata.create_all(bind=engine)


def insert_query(concept: str, explanation: str, model: str):
    """
    Insert a query and explanation into the database.
    """
    db = SessionLocal()

    query = QueryModel(
        concept=concept,
        explanation=explanation,
        model=model
    )

    db.add(query)
    db.commit()
    db.close()