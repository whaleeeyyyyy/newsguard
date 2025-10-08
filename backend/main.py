import os
from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from backend.db import init_db, get_db, Article  # ← CORRECT import
from backend.newsapi_client import fetch_top_headlines
from backend.hf_client import summarize, sentiment, bias  # ← CORRECT import
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy import func, and_, or_

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

class SearchResponse(BaseModel):
    articles: List[ArticleResponse]
    total_count: int
    page: int
    limit: int
    filters_applied: dict

class StatsResponse(BaseModel):
    total_articles: int
    enriched_articles: int
    sentiment_distribution: dict
    bias_distribution: dict
    top_sources: List[dict]
    articles_by_date: List[dict]

@app.get("/news/search", response_model=SearchResponse, dependencies=[Depends(verify_api_key)])
def search_articles(
    q: Optional[str] = Query(None, description="Search in title and content"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment: POSITIVE, NEGATIVE, NEUTRAL"),
    bias: Optional[str] = Query(None, description="Filter by bias: left, center, right, neutral"),
    source: Optional[str] = Query(None, description="Filter by news source"),
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("published_at", description="Sort by: published_at, created_at, title"),
    order: str = Query("desc", description="Order: asc, desc"),
    db: Session = Depends(get_db)
):
    """Advanced search with multiple filters"""
    try:
        # Build base query
        query = db.query(Article)
        filters_applied = {}
        
        # Text search in title and content
        if q:
            search_filter = or_(
                Article.title.ilike(f"%{q}%"),
                Article.raw_text.ilike(f"%{q}%")
            )
            query = query.filter(search_filter)
            filters_applied["search_query"] = q
        
        # Sentiment filter
        if sentiment:
            query = query.filter(Article.sentiment == sentiment.upper())
            filters_applied["sentiment"] = sentiment.upper()
        
        # Bias filter
        if bias:
            query = query.filter(Article.bias == bias.lower())
            filters_applied["bias"] = bias.lower()
        
        # Source filter
        if source:
            query = query.filter(Article.source.ilike(f"%{source}%"))
            filters_applied["source"] = source
        
        # Date range filters
        if from_date:
            try:
                from_dt = datetime.fromisoformat(from_date)
                query = query.filter(Article.published_at >= from_dt)
                filters_applied["from_date"] = from_date
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
        
        if to_date:
            try:
                to_dt = datetime.fromisoformat(to_date + " 23:59:59")
                query = query.filter(Article.published_at <= to_dt)
                filters_applied["to_date"] = to_date
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")
        
        # Get total count before pagination
        total_count = query.count()
        
        # Sorting
        if sort_by == "published_at":
            sort_column = Article.published_at
        elif sort_by == "created_at":
            sort_column = Article.created_at
        elif sort_by == "title":
            sort_column = Article.title
        else:
            sort_column = Article.published_at
        
        if order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())
        
        # Pagination
        offset = (page - 1) * limit
        articles = query.offset(offset).limit(limit).all()
        
        return SearchResponse(
            articles=articles,
            total_count=total_count,
            page=page,
            limit=limit,
            filters_applied=filters_applied
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/news/stats", response_model=StatsResponse, dependencies=[Depends(verify_api_key)])
def get_statistics(db: Session = Depends(get_db)):
    """Get analytics and statistics"""
    try:
        # Basic counts
        total_articles = db.query(Article).count()
        enriched_articles = db.query(Article).filter(Article.summary.isnot(None)).count()
        
        # Sentiment distribution
        sentiment_data = db.query(
            Article.sentiment, 
            func.count(Article.sentiment)
        ).filter(
            Article.sentiment.isnot(None)
        ).group_by(Article.sentiment).all()
        
        sentiment_distribution = {
            sentiment or "Unknown": count for sentiment, count in sentiment_data
        }
        
        # Bias distribution
        bias_data = db.query(
            Article.bias, 
            func.count(Article.bias)
        ).filter(
            Article.bias.isnot(None)
        ).group_by(Article.bias).all()
        
        bias_distribution = {
            bias or "Unknown": count for bias, count in bias_data
        }
        
        # Top sources
        source_data = db.query(
            Article.source, 
            func.count(Article.source)
        ).filter(
            Article.source.isnot(None)
        ).group_by(Article.source).order_by(
            func.count(Article.source).desc()
        ).limit(10).all()
        
        top_sources = [
            {"source": source, "count": count} 
            for source, count in source_data
        ]
        
        # Articles by date (last 7 days)
        from datetime import timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        daily_data = db.query(
            func.date(Article.published_at).label('date'),
            func.count(Article.id).label('count')
        ).filter(
            Article.published_at >= week_ago
        ).group_by(
            func.date(Article.published_at)
        ).order_by('date').all()
        
        articles_by_date = [
            {"date": str(date), "count": count} 
            for date, count in daily_data
        ]
        
        return StatsResponse(
            total_articles=total_articles,
            enriched_articles=enriched_articles,
            sentiment_distribution=sentiment_distribution,
            bias_distribution=bias_distribution,
            top_sources=top_sources,
            articles_by_date=articles_by_date
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats generation failed: {str(e)}")

@app.get("/news/sources", dependencies=[Depends(verify_api_key)])
def get_sources(db: Session = Depends(get_db)):
    """Get list of available news sources"""
    try:
        sources = db.query(Article.source, func.count(Article.source)).filter(
            Article.source.isnot(None)
        ).group_by(Article.source).order_by(Article.source).all()
        
        return {
            "sources": [
                {"name": source, "article_count": count} 
                for source, count in sources
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sources: {str(e)}")

@app.middleware("http")
async def log_requests(request, call_next):
    response = await call_next(request)
    logging.info(f"{request.client.host} - {request.method} {request.url} - {response.status_code}")
    return response

@app.get("/", dependencies=[Depends(verify_api_key)])
def read_root():
    return {
        "message": "NewsGuard AI Backend is running!",
        "version": "1.0.0",
        "new_features": {
            "search": "/news/search - Advanced search with filters",
            "stats": "/news/stats - Analytics dashboard data",
            "sources": "/news/sources - Available news sources",
            "examples": "/news/test-search - API usage examples"
        },
        "endpoints": [
            "/news/fetch", 
            "/news", 
            "/news/search",
            "/news/stats",
            "/news/sources",
            "/news/enrich/{id}", 
            "/news/enrich_all"
        ]
    }

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
def list_articles(
    limit: int = Query(20, ge=1, le=100),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment"),
    bias: Optional[str] = Query(None, description="Filter by bias"),
    enriched_only: bool = Query(False, description="Show only enriched articles"),
    db: Session = Depends(get_db)
):
    """List articles with optional filters"""
    query = db.query(Article)
    
    # Apply filters
    if sentiment:
        query = query.filter(Article.sentiment == sentiment.upper())
    
    if bias:
        query = query.filter(Article.bias == bias.lower())
    
    if enriched_only:
        query = query.filter(Article.summary.isnot(None))
    
    articles = query.order_by(Article.published_at.desc()).limit(limit).all()
    return articles

@app.post("/news/enrich/{article_id}", dependencies=[Depends(verify_api_key)])
def enrich_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if not article.raw_text:
        raise HTTPException(status_code=400, detail="No text to analyze")
    try:
        # Use your existing hf_client functions
        s = summarize(article.raw_text)      # ← Your working code
        sent = sentiment(article.raw_text)   # ← Your working code
        b = bias(article.raw_text)          # ← Your working code
        
        article.summary = s
        article.sentiment = sent
        article.bias = b
        db.commit()
        return {"id": article.id, "summary": s, "sentiment": sent, "bias": b}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")

@app.post("/news/enrich_all", dependencies=[Depends(verify_api_key)])
def enrich_all(limit: int = 10, db: Session = Depends(get_db)):
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
            logging.exception(f"Error enriching article {article.id}: {e}")
    db.commit()
    return {"enriched_articles": enriched}

@app.get("/_debug/health")
def debug_health(db: Session = Depends(get_db)):
    import os
    return {
        "db_connected": True,
        "hf_token_present": bool(os.getenv("HF_TOKEN")),
    }

@app.get("/news/test-search", dependencies=[Depends(verify_api_key)])
def test_search_examples():
    """Examples of how to use the search endpoint"""
    return {
        "examples": {
            "basic_search": "/news/search?q=politics",
            "sentiment_filter": "/news/search?sentiment=POSITIVE",
            "bias_filter": "/news/search?bias=center",
            "source_filter": "/news/search?source=CNN",
            "date_range": "/news/search?from_date=2024-01-01&to_date=2024-01-31",
            "combined": "/news/search?q=economy&sentiment=NEGATIVE&bias=left&limit=10",
            "pagination": "/news/search?page=2&limit=5",
            "sorting": "/news/search?sort_by=title&order=asc"
        },
        "available_filters": {
            "sentiment": ["POSITIVE", "NEGATIVE", "NEUTRAL"],
            "bias": ["left", "center", "right", "neutral"],
            "sort_by": ["published_at", "created_at", "title"],
            "order": ["asc", "desc"]
        }
    }