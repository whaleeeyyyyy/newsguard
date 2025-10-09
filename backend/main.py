from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import aiohttp, redis.asyncio as redis, json, os, logging, datetime

from supabase import create_client, Client
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# create log directory relative to project root (one level above backend/)
ROOT = Path(__file__).resolve().parents[1]  # project root: .../newsguard
LOG_DIR = ROOT / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "app.log"

# Configure root logger with rotating file handler + console output
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Rotating file handler (5 files * 2MB = 10MB total)
file_handler = RotatingFileHandler(str(LOG_FILE), maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8")
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler for dev output
console_handler = logging.StreamHandler()
console_handler.setFormatter(file_formatter)
logger.addHandler(console_handler)

# Now you can use logging.info(...) as before
logging.info("Logging initialized. Log file: %s", LOG_FILE)

# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
HF_API_URL = os.getenv("HF_API_URL", "https://api-inference.huggingface.co/models/facebook/bart-large-cnn")
HF_API_KEY = os.getenv("HF_API_KEY", "")
API_KEY = os.getenv("API_KEY", "test123")

# ---------------------------------------------------------------------
# APP SETUP
# ---------------------------------------------------------------------
app = FastAPI(title="NewsGuard API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    filename="log/app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
# ---------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------
class Article(BaseModel):
    id: Optional[int]
    title: str
    content: str
    summary: Optional[str] = None
    enriched: bool = False

# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------
async def enrich_article(article_id: int):
    """Enrich an article using Hugging Face summarization."""
    async with app.state.db.acquire() as conn:
        article = await conn.fetchrow("SELECT * FROM articles WHERE id = $1", article_id)
        if not article:
            logging.error(f"Article {article_id} not found.")
            return

        text = article["content"]
        async with aiohttp.ClientSession() as session:
            async with session.post(
                HF_API_URL,
                headers={"Authorization": f"Bearer {HF_API_KEY}"},
                json={"inputs": text},
            ) as response:
                if response.status != 200:
                    logging.error(f"HuggingFace error {response.status}")
                    return

                data = await response.json()
                summary = data[0]["summary_text"] if isinstance(data, list) else data.get("summary_text", "")
                await conn.execute(
                    "UPDATE articles SET summary=$1, enriched=true WHERE id=$2", summary, article_id
                )
                logging.info(f"Article {article_id} enriched successfully.")

# ---------------------------------------------------------------------
# AUTH DECORATOR
# ---------------------------------------------------------------------
async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

# ---------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------
@app.get("/health")
async def health_check():
    try:
        # Simple Supabase test query (fetch one row)
        response = supabase.table("news").select("id").limit(1).execute()
        if response.data is not None:
            return {"status": "ok", "detail": "Supabase connection successful"}
        else:
            return {"status": "warning", "detail": "No data found, but Supabase reachable"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# ---------------------------------------------------------------------
# NEWS CRUD
# ---------------------------------------------------------------------
@app.get("/news/", response_model=List[dict])
async def get_articles(category: str = Query(None, description="Optional category filter")):
    """
    Fetch articles from the Supabase 'news' table.
    Optionally filter by category (?category=tech)
    """
    query = supabase.table("news").select("*")
    
    if category:
        query = query.eq("category", category)
    
    response = query.execute()
    return response.data
    
@app.get("/test_supabase")
def test_supabase():
    response = supabase.table("news").select("*").limit(1).execute()
    return {"status": "ok", "data": response.data}


@app.get("/news/{article_id}", response_model=Article)
async def get_article(article_id: int):
    cached = await app.state.redis.get(f"article:{article_id}")
    if cached:
        return json.loads(cached)

    async with app.state.db.acquire() as conn:
        article = await conn.fetchrow("SELECT * FROM articles WHERE id=$1", article_id)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        data = dict(article)
        await app.state.redis.set(f"article:{article_id}", json.dumps(data), ex=3600)
        return data

@app.post("/news/", dependencies=[Depends(verify_api_key)])
async def add_article(article: Article, background_tasks: BackgroundTasks):
    async with app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO articles (title, content, summary, enriched) VALUES ($1,$2,$3,$4) RETURNING id",
            article.title, article.content, article.summary, article.enriched
        )
        article_id = row["id"]
        background_tasks.add_task(enrich_article, article_id)
        return {"message": "Article added", "id": article_id}

@app.post("/news/enrich/{article_id}", dependencies=[Depends(verify_api_key)])
async def enrich_one(article_id: int):
    await enrich_article(article_id)
    return {"message": f"Article {article_id} enriched"}

@app.post("/news/enrich_all", dependencies=[Depends(verify_api_key)])
async def enrich_all():
    async with app.state.db.acquire() as conn:
        ids = await conn.fetch("SELECT id FROM articles WHERE enriched=false")
        for row in ids:
            await enrich_article(row["id"])
    return {"message": f"Triggered enrichment for {len(ids)} articles"}

# ---------------------------------------------------------------------
# NEWS ANALYTICS
# ---------------------------------------------------------------------
@app.get("/news/stats")
async def get_stats():
    async with app.state.db.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM articles")
        enriched = await conn.fetchval("SELECT COUNT(*) FROM articles WHERE enriched=true")
        pending = total - enriched
        rate = round(enriched / total, 2) if total > 0 else 0
    return {
        "total_articles": total,
        "enriched_articles": enriched,
        "pending_articles": pending,
        "success_rate": rate,
    }

@app.post("/news/refresh_all", dependencies=[Depends(verify_api_key)])
async def refresh_all():
    async with app.state.db.acquire() as conn:
        ids = await conn.fetch("SELECT id FROM articles")
        for row in ids:
            await enrich_article(row["id"])
    return {"message": f"Refreshed {len(ids)} articles"}

# ---------------------------------------------------------------------
# CACHE MANAGEMENT
# ---------------------------------------------------------------------
@app.get("/cache/stats")
async def cache_stats():
    info = await app.state.redis.info()
    return {
        "keys": await app.state.redis.dbsize(),
        "used_memory_human": info.get("used_memory_human"),
        "hits": info.get("keyspace_hits"),
        "misses": info.get("keyspace_misses"),
    }

@app.post("/cache/clear", dependencies=[Depends(verify_api_key)])
async def cache_clear():
    await app.state.redis.flushdb()
    return {"message": "Cache cleared"}

# ---------------------------------------------------------------------
# LOG ACCESS (OPTIONAL)
# ---------------------------------------------------------------------
@app.get("/logs/recent")
async def recent_logs():
    try:
        with open("log/app.log", "r") as f:
            lines = f.readlines()[-20:]
        return {"logs": lines}
    except FileNotFoundError:
        return {"logs": []}
