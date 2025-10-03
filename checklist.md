NewsGuard AI — a deployed web app that fetches live headlines, summarizes articles, detects sentiment, and classifies bias so users can compare coverage across outlets.

Exact tech choices (fastest path)

Frontend: React + Vite + Tailwind CSS (Vercel deploy)

Backend: FastAPI (Python) (Render or Railway deploy)

DB: Supabase (Postgres + optional pgvector later) — or plain Postgres

HuggingFace: HuggingFace Inference API (avoid hosting models yourself)

News source: NewsAPI (or GNews if you prefer)

Cache: Redis (optional; use Render’s Redis or a simple in-memory LRU for MVP)

Auth: none for MVP (optional GitHub/Firebase later)

CI: GitHub Actions (deploy on push to main)

Recommended HuggingFace models (use with Inference API)

Summarization: facebook/bart-large-cnn (solid general summarizer)

Sentiment: distilbert-base-uncased-finetuned-sst-2-english (binary sentiment)

Bias classification (zero-shot): facebook/bart-large-mnli (zero-shot classification; labels e.g. ["left","center","right","neutral"])

Embeddings (optional for searching/grouping): sentence-transformers/all-MiniLM-L6-v2

(Using the HF Inference API means you call endpoints like /summarization or /zero-shot-classification with these model names.)

7-day plan — shipable MVP (one developer)
Day 1 — Setup & design (scaffold)

Create GitHub repo, add README template.

Scaffold frontend: npm create vite@latest newsguard --template react + Tailwind setup.

Scaffold backend FastAPI: create basic app, uvicorn run script, .env gitignored.

Acquire API keys: NewsAPI and HuggingFace token.

Quick wireframe: list view of articles + dashboard with 2 charts (bias pie, sentiment bar).

Deliverable: repo with frontend + backend skeleton, wireframes, keys stored locally.

Day 2 — News ingestion & DB

Implement NewsAPI ingestion endpoint in backend: GET /news/fetch?source=top saves article metadata (title, url, content, source, published_at).

Minimal DB schema (Postgres/Supabase): articles(id, title, url, source, published_at, raw_text, summary, sentiment, bias, created_at).

Endpoint to list articles: GET /news (paginated).

Deliverable: backend can fetch & store headlines; frontend shows raw list via /news.

Day 3 — HuggingFace proxy + summarization

Implement HF proxy endpoints in backend (caching):

POST /hf/summarize { text } → calls HF model facebook/bart-large-cnn

POST /hf/sentiment { text } → calls HF model distilbert-...-sst-2

POST /hf/zero-shot { text, labels } → calls facebook/bart-large-mnli

In ingestion pipeline, call summarization immediately and store summary.

Add simple caching: hash the text → store summary result in DB or in-memory map.

Deliverable: stored summaries shown in article list.

Day 4 — Sentiment & bias classification + UI

Extend ingestion to compute sentiment and bias (zero-shot with labels ["left", "center", "right", "neutral"]).

Frontend: article card displays title, source, summary, sentiment badge (Positive/Negative/Neutral), bias badge (Left/Center/Right/Neutral).

Add loading states and error handling.

Deliverable: articles show summary + sentiment + bias badges.

Day 5 — Dashboard & comparison view

Build dashboard:

Bias distribution pie chart (counts of left/center/right/neutral).

Sentiment bar chart (counts).

Implement “compare” feature: user can pick an article and show same topic across sources (match by title similarity or search query).

Add export/save button to save article to “analysis” list (optional small user state).

Deliverable: dashboard visuals + simple compare view.

Day 6 — Polish, caching & rate limit handling

Add better caching for HF calls (Redis or simple file cache). Key = task|sha256(text)|params.

Add basic rate-limit/backoff: if HF returns rate-limit, retry with exponential backoff or queue and return "processing" state.

UI polishing: responsive layout, colors, microcopy.

Create demo GIF script and record a 45–60s GIF.

Deliverable: stable app, caching implemented, demo GIF.

Day 7 — Deploy & docs

Deploy backend (Render/Railway). Set env vars (HF token, NewsAPI key).

Deploy frontend to Vercel (connect to repo).

Final README: install, run, env vars, demo GIF, architecture small diagram.

Create 2–3 resume bullets and 280-char blurb.

Tag release on GitHub.

Deliverable: live deployed demo + README + portfolio assets.
