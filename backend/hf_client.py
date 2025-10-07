# backend/hf_client.py (dev logging version)
import os, requests, time, logging
from hashlib import sha256
from dotenv import load_dotenv

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN", "")
if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN not found in environment (.env)")

# Logging to file for HF responses & errors
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "hf_debug.log")
logger = logging.getLogger("hf_client")
logger.setLevel(logging.INFO)
# file handler
fh = logging.FileHandler(LOG_PATH)
fh.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
# avoid duplicate handlers
if not logger.handlers:
    logger.addHandler(fh)

HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}
CACHE = {}
CACHE_TTL_SECONDS = 60 * 60 * 24

def _make_cache_key(task: str, text: str, params: dict | None = None) -> str:
    h = sha256((text or "").encode("utf-8")).hexdigest()
    key = f"{task}:{h}"
    if params:
        key += ":" + sha256(str(params).encode("utf-8")).hexdigest()
    return key

def _get_cached(key: str):
    item = CACHE.get(key)
    if not item:
        return None
    ts, value = item
    if time.time() - ts > CACHE_TTL_SECONDS:
        del CACHE[key]
        return None
    return value

def _set_cache(key: str, value):
    CACHE[key] = (time.time(), value)

def _is_transient_status(status: int) -> bool:
    return status in (404, 429, 500, 502, 503)

def _hf_request(model: str, payload: dict, task: str, max_retries: int = 4, base_backoff: float = 1.0):
    key = _make_cache_key(task, payload.get("inputs", "") or payload.get("text", ""), payload.get("parameters"))
    cached = _get_cached(key)
    if cached is not None:
        logger.info("HF CACHE HIT %s (task=%s)", key, task)
        return cached

    url = f"https://api-inference.huggingface.co/models/{model}"
    attempt = 0
    while True:
        attempt += 1
        try:
            r = requests.post(url, headers=HEADERS, json=payload, timeout=60)
        except requests.RequestException as e:
            logger.warning("HF request exception (attempt %d): %s", attempt, str(e))
            if attempt >= max_retries:
                logger.exception("HF request failed after %d attempts: %s", attempt, e)
                raise RuntimeError(f"HF request failed after {attempt} attempts: {e}")
            time.sleep(base_backoff * (2 ** (attempt - 1)))
            continue

        status = r.status_code
        body = r.text
        # log raw response body for debugging
        logger.info("HF model=%s attempt=%d status=%s body=%s", model, attempt, status, body[:2000])

        if 200 <= status < 300:
            try:
                res = r.json()
            except ValueError:
                res = r.text
            _set_cache(key, res)
            return res

        # transient -> retry
        if _is_transient_status(status) and attempt < max_retries:
            backoff = base_backoff * (2 ** (attempt - 1))
            jitter = backoff * 0.1 * (1 + (attempt % 2))
            sleep_time = backoff + jitter
            logger.info("Retrying HF request in %.1f seconds (attempt %d/%d)", sleep_time, attempt, max_retries)
            time.sleep(sleep_time)
            continue

        # not recoverable or exhausted retries: raise with details
        logger.error("HF API unrecoverable error model=%s status=%s body=%s", model, status, body[:2000])
        raise RuntimeError(f"HF API Error {status}: {body}")

# safe trimming helpers
def _safe_trim_text(text: str, max_chars: int = 3500) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    trimmed = text[:max_chars]
    last_period = trimmed.rfind(".")
    if last_period > int(max_chars * 0.6):
        return trimmed[:last_period+1]
    return trimmed

def summarize(text: str) -> str:
    if not text:
        return ""
    if len(text) > 4000:
        chunk_size = 3000
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        summaries = []
        for c in chunks:
            payload = {"inputs": _safe_trim_text(c, max_chars=3000), "parameters": {"max_length": 120, "min_length": 30}}
            res = _hf_request("facebook/bart-large-cnn", payload, task="summarization")
            if isinstance(res, list) and res and "summary_text" in res[0]:
                summaries.append(res[0]["summary_text"])
            else:
                summaries.append(str(res)[:1000])
        combined = " ".join(summaries)
        payload = {"inputs": _safe_trim_text(combined, max_chars=3000), "parameters": {"max_length": 120, "min_length": 30}}
        res2 = _hf_request("facebook/bart-large-cnn", payload, task="summarization")
        if isinstance(res2, list) and res2 and "summary_text" in res2[0]:
            return res2[0]["summary_text"]
        return str(res2)
    payload = {"inputs": _safe_trim_text(text, max_chars=3500), "parameters": {"max_length": 120, "min_length": 30}}
    res = _hf_request("facebook/bart-large-cnn", payload, task="summarization")
    if isinstance(res, list) and res and "summary_text" in res[0]:
        return res[0]["summary_text"]
    return str(res)

def sentiment(text: str) -> str:
    if not text:
        return "NEUTRAL"
    payload = {"inputs": _safe_trim_text(text, max_chars=3500)}
    res = _hf_request("distilbert-base-uncased-finetuned-sst-2-english", payload, task="sentiment")
    if isinstance(res, list) and res:
        return res[0].get("label", str(res))
    return str(res)

def bias(text: str) -> str:
    if not text:
        return "neutral"
    labels = ["left", "center", "right", "neutral"]
    payload = {"inputs": _safe_trim_text(text, max_chars=3500), "parameters": {"candidate_labels": labels}}
    res = _hf_request("facebook/bart-large-mnli", payload, task="zero_shot")
    if isinstance(res, dict) and "labels" in res:
        return res.get("labels", ["neutral"])[0]
    return str(res)
