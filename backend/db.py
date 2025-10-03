import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")  # Supabase connection URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"},  # required for Supabase
    pool_pre_ping=True,
    echo=True  # remove in production
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), unique=True, nullable=False)
    source = Column(String(200), nullable=True)
    published_at = Column(DateTime, default=datetime.utcnow)
    raw_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    sentiment = Column(String(50), nullable=True)
    bias = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"❌ Database creation error: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
