from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    url = Column(String(1000), unique=True, nullable=False, index=True)
    source = Column(String(100), nullable=True, index=True)
    author = Column(String(200), nullable=True)
    published_at = Column(DateTime, default=datetime.utcnow, index=True)
    raw_text = Column(Text, nullable=True)
    
    # AI Analysis Results
    summary = Column(Text, nullable=True)
    sentiment = Column(String(20), nullable=True, index=True)
    bias = Column(String(20), nullable=True, index=True)
    confidence_score = Column(Float, nullable=True)
    
    # Metadata
    is_enriched = Column(Boolean, default=False, index=True)
    enriched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title[:50]}...')>"