from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import aioredis
import logging
import os

from backend.db import init_db, get_db, Article
from backend.newsapi_client import fetch_top_headlines
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Initialize database
init_db()

# Setup logging
logging.basicConfig(level=logging.INFO, filename="api_access.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

# FastAPI app
app = FastAPI(
    title="NewsGuard AI Backend",
    description="AI-powered news analysis platform",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key verification
API_KEY = os.getenv("NEWSGUARD_API_KEY", "test123")  # Default key for dev/testing

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

# Rate limiter startup
@app.on_event("startup")
async def startup():
    redis = await aioredis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis)

# Pydantic models
class ArticleResponse(BaseModel):
    id: int
    title: str
    url: str
    source: Optional[str]
    published_at: datetime
    summary: Optional[str]
    sentiment: Optional[str]
    bias: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class FetchResponse(BaseModel):
    ingested: int
    message: str

# Middleware for request logging
@app.middleware("http")
async def log_requests(request, call_next):
    response = await call_next(request)
    logging.info(f"{request.client.host} - {request.method} {request.url} - {response.status_code}")
    return response

# Root endpoint
@app.get("/", dependencies=[Depends(verify_api_key)])
def read_root():
    return {"message": "NewsGuard AI Backend is running!"}

# Fetch news from NewsAPI
@app.get("/news/fetch", response_model=FetchResponse,
         dependencies=[Depends(verify_api_key), Depends(RateLimiter(times=5, seconds=60))])
def fetch_news(q: Optional[str] = None, country: str = "us", db: Session = Depends(get_db)):
    try:
        articles = fetch_top_headlines(country=country, q=q, page_size=10)
        count = 0
        for article_data in articles:
            if not article_data.get("url") or not article_data.get("title"):
                continue
            exists = db.query(Article).filter(Article.url == article_data["url"]).first()
            if exists:
                continue
            published_at = None
            try:
                if article_data.get("publishedAt"):
                    published_str = article_data["publishedAt"].replace("Z", "+00:00")
                    published_at = datetime.fromisoformat(published_str)
            except (ValueError, AttributeError):
                published_at = datetime.utcnow()
            article = Article(
                title=article_data["title"],
                url=article_data["url"],
                source=article_data.get("source", {}).get("name"),
                published_at=published_at,
                raw_text=article_data.get("content") or article_data.get("description") or ""
            )
            db.add(article)
            count += 1
        db.commit()
        return {"ingested": count, "message": f"Successfully ingested {count} new articles"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# List articles
@app.get("/news", response_model=List[ArticleResponse],
         dependencies=[Depends(verify_api_key)])
def list_articles(limit: int = 20, db: Session = Depends(get_db)):
    articles = db.query(Article).order_by(Article.published_at.desc()).limit(limit).all()
    return articles

# Get article by ID
@app.get("/news/{article_id}", response_model=ArticleResponse,
         dependencies=[Depends(verify_api_key)])
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

# Search articles by keyword (Day 4)
@app.get("/news/search", response_model=List[ArticleResponse],
         dependencies=[Depends(verify_api_key), Depends(RateLimiter(times=10, seconds=60))])
def search_articles(q: str = Query(...), page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    query = db.query(Article).filter(
        Article.title.ilike(f"%{q}%") | Article.raw_text.ilike(f"%{q}%")
    ).order_by(Article.published_at.desc())
    articles = query.offset((page-1)*limit).limit(limit).all()
    return articles
