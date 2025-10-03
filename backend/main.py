# backend/app/main.py
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
import requests
from backend.db import SessionLocal, engine  
from sqlalchemy.orm import Session
from .models import Article
from fastapi import HTTPException
from backend.hf_client import summarize, sentiment, bias
from backend.db import SessionLocal, Article


load_dotenv()  # loads .env in project root when running from project root

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")

if not NEWSAPI_KEY:
    raise RuntimeError("NEWSAPI_KEY not set in environment")
if not HF_TOKEN:
    # Not fatal — you can still run basic fetch without HF summarization,
    # but for summarization HF_TOKEN is required. Uncomment raise if you want strict enforcement.
    # raise RuntimeError("HF_TOKEN not set in environment")
    pass

app = FastAPI(title="NewsGuard AI Backend")

class FetchResponse(BaseModel):
    ingested: int
    summaries: dict | None = None

@app.get("/health")
def health():
    return {"status": "ok"}

def fetch_headlines_from_newsapi(query: str = "world", page_size: int = 5):
    """Return a list of articles (title + description + url). Uses NewsAPI.org top-headlines / everything endpoint."""
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "pageSize": page_size,
        "language": "en",
        "sortBy": "relevancy",
        "apiKey": NEWSAPI_KEY,
    }
    r = requests.get(url, params=params, timeout=10)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"NewsAPI error: {r.status_code} {r.text}")
    data = r.json()
    articles = data.get("articles", [])
    results = []
    for a in articles:
        results.append({
            "title": a.get("title"),
            "description": a.get("description"),
            "url": a.get("url"),
            "source": a.get("source", {}).get("name"),
        })
    return results

def summarize_with_hf(text: str, model: str = "facebook/bart-large-cnn"):
    """Call Hugging Face Inference API to summarize text. Returns string summary or None on failure."""
    if not HF_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": text}
    hf_url = f"https://api-inference.huggingface.co/models/{model}"
    r = requests.post(hf_url, headers=headers, json=payload, timeout=20)
    if r.status_code != 200:
        # return None or raise depending on your preference
        return None
    resp = r.json()
    # Many summarization models return a list of dicts with "summary_text"
    if isinstance(resp, list) and len(resp) > 0 and isinstance(resp[0], dict):
        return resp[0].get("summary_text") or resp[0].get("generated_text")
    # If HF returns other shapes, try to pick something
    if isinstance(resp, dict) and "summary_text" in resp:
        return resp["summary_text"]
    return None

@app.get("/news/fetch", response_model=FetchResponse)
def fetch_news(q: str = Query("world", description="Search query"),
               limit: int = Query(5, ge=1, le=20, description="Number of articles to fetch")):
    # 1) Fetch headlines
    articles = fetch_headlines_from_newsapi(query=q, page_size=limit)

    # 2) Optionally summarize each article description (or title if no description)
    summaries = {}
    for i, art in enumerate(articles):
        text_to_summarize = art.get("description") or art.get("title") or ""
        if not text_to_summarize:
            summaries[i] = None
            continue
        summary = summarize_with_hf(text_to_summarize)
        summaries[i] = summary

    # placeholder: ingest into DB later
    ingested = len(articles)

    return {"ingested": ingested, "summaries": summaries}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def root(db: Session = Depends(get_db)):
    count = db.query(Article).count()
    return {"message": f"There are {count} articles in the database."}

@app.post("/news/enrich/{article_id}")
def enrich_article(article_id: int):
    db = SessionLocal()
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        db.close()
        raise HTTPException(status_code=404, detail="Article not found")
    if not article.raw_text:
        db.close()
        raise HTTPException(status_code=400, detail="No text to analyze")
    
    # HuggingFace enrichment
    article.summary = summarize(article.raw_text)
    article.sentiment = sentiment(article.raw_text)
    article.bias = bias(article.raw_text)

    db.commit()
    db.close()
    return {
        "id": article.id,
        "summary": article.summary,
        "sentiment": article.sentiment,
        "bias": article.bias
    }

@app.post("/news/enrich_all")
def enrich_all(limit: int = 10):
    db = SessionLocal()
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
            print(f"Error enriching {article.id}: {e}")
    db.commit()
    db.close()
    return {"enriched_articles": enriched}