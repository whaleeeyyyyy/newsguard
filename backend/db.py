from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

# Local Postgres connection
DATABASE_URL = "postgresql://newsguard_user:newsguard_password123@localhost:5432/newsguard_db"

# SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=True)  # echo=True prints SQL queries

# Session class for database operations
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()

# -------------------
# Article model
# -------------------
class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    url = Column(String, unique=True, nullable=False)
    source = Column(String, nullable=True)
    published_at = Column(DateTime, default=datetime.utcnow)
    raw_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    sentiment = Column(String, nullable=True)
    bias = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables if not exist
def init_db():
    Base.metadata.create_all(bind=engine)
