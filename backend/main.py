# backend/main.py
import os
from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from backend.db import init_db, get_db, Article
from backend.newsapi_client import fetch_top_headlines
from backend.hf_client import summarize, sentiment, bias
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Initialize DB (creates tables if needed)
init_db()

# logging
logging.basicConfig(level=logging.INFO, filename="api_access.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

API_KEY = os.getenv("NEWSGUARD_API_KEY", "test123")

app = FastAPI(title="NewsGuard AI Backend", version="1.0.0")

# CORS (adjust origin as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

# Pydantic responses
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

@app.middleware("http")
async def log_requests(request, call_next):
    response = await call_next(request)
    logging.info(f"{request.client.host} - {request.method} {request.url} - {response.status_code}")
    return response

@app.get("/", dependencies=[Depends(verify_api_key)])
def read_root():
    return {"message": "NewsGuard AI Backend is running!"}

@app.get("/news/fetch", response_model=FetchResponse, dependencies=[Depends(verify_api_key)])
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
                source=(article_data.get("source") or {}).get("name") if article_data.get("source") else None,
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

@app.get("/news", response_model=List[ArticleResponse], dependencies=[Depends(verify_api_key)])
def list_articles(limit: int = 20, db: Session = Depends(get_db)):
    articles = db.query(Article).order_by(Article.published_at.desc()).limit(limit).all()
    return articles

@app.post("/news/enrich/{article_id}", dependencies=[Depends(verify_api_key)])
def enrich_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if not article.raw_text:
        raise HTTPException(status_code=400, detail="No text to analyze")
    try:
        s = summarize(article.raw_text)
        sent = sentiment(article.raw_text)
        b = bias(article.raw_text)
        article.summary = s
        article.sentiment = sent
        article.bias = b
        db.commit()
        return {"id": article.id, "summary": s, "sentiment": sent, "bias": b}
    except Exception as e:
        db.rollback()
        # DEV: return error detail and hint; in prod, return generic message only
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")


@app.post("/news/enrich_all", dependencies=[Depends(verify_api_key)])
def enrich_all(limit: int = 10, db: Session = Depends(get_db)):
    # find un-enriched articles (summary is NULL)
    articles = db.query(Article).filter(Article.summary.is_(None)).limit(limit).all()
    enriched = []
    for article in articles:
        if not article.raw_text:
            continue
        try:
            article.summary = summarize(article.raw_text)
            article.sentiment = sentiment(article.raw_text)
            article.bias = bias(article.raw_text)
            enriched.append(article.id)
        except Exception as e:
            # continue on errors but log them
            logging.exception(f"Error enriching article {article.id}: {e}")
    db.commit()
    return {"enriched_articles": enriched}

@app.get("/_debug/health")
def debug_health(db: Session = Depends(get_db)):
    import os
    from backend.hf_client import _get_cached  # or just import HF_TOKEN
    return {
        "db_connected": True,   # if get_db didn't raise
        "hf_token_present": bool(os.getenv("HF_TOKEN")),
        "sample_cache_keys": list(_get_cached.__name__ if hasattr(_get_cached,'__name__') else [])[:5]
    }

