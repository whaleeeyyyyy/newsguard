from sqlalchemy import Column, Integer, String, Text, DateTime
from .db import Base
import datetime

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False, unique=True)
    summary = Column(Text)
    published_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Article(title={self.title}, url={self.url})>"
