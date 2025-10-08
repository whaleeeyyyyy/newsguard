import os, requests, time, logging
from hashlib import sha256
from dotenv import load_dotenv

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN", "")
if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN not found in environment (.env)")

# Better logging setup
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "hf_debug.log")
logger = logging.getLogger("hf_client")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fh = logging.FileHandler(LOG_PATH)
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}
CACHE = {}
CACHE_TTL_SECONDS = 60 * 60 * 24

# [Keep all your existing cache functions - they're good!]
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

# IMPROVED: Better model handling and error messages
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
        logger.info("HF model=%s attempt=%d status=%s body=%s", model, attempt, status, body[:500])

        if 200 <= status < 300:
            try:
                res = r.json()
            except ValueError:
                res = r.text
            _set_cache(key, res)
            return res

        # IMPROVED: Better 404 handling
        if status == 404:
            logger.error("Model %s not found or not accessible. Check model name and token permissions.", model)
            raise RuntimeError(f"Model {model} not found (404). Check model name and HF token permissions.")
        
        # Model loading (503)
        if status == 503 and "loading" in body.lower():
            logger.info("Model %s is loading, waiting longer...", model)
            time.sleep(20)  # Wait longer for model loading
            continue

        # Other transient errors
        if _is_transient_status(status) and attempt < max_retries:
            backoff = base_backoff * (2 ** (attempt - 1))
            jitter = backoff * 0.1 * (1 + (attempt % 2))
            sleep_time = backoff + jitter
            logger.info("Retrying HF request in %.1f seconds (attempt %d/%d)", sleep_time, attempt, max_retries)
            time.sleep(sleep_time)
            continue

        logger.error("HF API unrecoverable error model=%s status=%s body=%s", model, status, body[:500])
        raise RuntimeError(f"HF API Error {status}: {body}")

# IMPROVED: Better model choices and error handling
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
    """IMPROVED: Better error handling and fallback"""
    if not text or len(text.strip()) < 50:
        return "Text too short to summarize"
    
    try:
        # Your existing chunking logic is good - keep it!
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
                    summaries.append(str(res)[:200])
            
            combined = " ".join(summaries)
            payload = {"inputs": _safe_trim_text(combined, max_chars=3000), "parameters": {"max_length": 120, "min_length": 30}}
            res2 = _hf_request("facebook/bart-large-cnn", payload, task="summarization")
            if isinstance(res2, list) and res2 and "summary_text" in res2[0]:
                return res2[0]["summary_text"]
            return str(res2)[:200]
        
        payload = {"inputs": _safe_trim_text(text, max_chars=3500), "parameters": {"max_length": 120, "min_length": 30}}
        res = _hf_request("facebook/bart-large-cnn", payload, task="summarization")
        if isinstance(res, list) and res and "summary_text" in res[0]:
            return res[0]["summary_text"]
        return str(res)[:200]
        
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return f"Summarization failed: {str(e)[:100]}"

def sentiment(text: str) -> str:
    """IMPROVED: More reliable sentiment model"""
    if not text:
        return "NEUTRAL"
    
    try:
        payload = {"inputs": _safe_trim_text(text, max_chars=1000)}
        # Try primary model first
        res = _hf_request("cardiffnlp/twitter-roberta-base-sentiment-latest", payload, task="sentiment")
        if isinstance(res, list) and res:
            label = res[0].get("label", "NEUTRAL")
            # Map labels to standard format
            if "POSITIVE" in label.upper() or "POS" in label.upper():
                return "POSITIVE"
            elif "NEGATIVE" in label.upper() or "NEG" in label.upper():
                return "NEGATIVE"
            return "NEUTRAL"
        return "NEUTRAL"
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        return "NEUTRAL"

def bias(text: str) -> str:
    """IMPROVED: Better bias detection"""
    if not text:
        return "neutral"
    
    try:
        labels = ["left-leaning", "center", "right-leaning", "neutral"]
        payload = {"inputs": _safe_trim_text(text, max_chars=1000), "parameters": {"candidate_labels": labels}}
        res = _hf_request("facebook/bart-large-mnli", payload, task="zero_shot")
        if isinstance(res, dict) and "labels" in res:
            return res.get("labels", ["neutral"])[0]
        return "neutral"
    except Exception as e:
        logger.error(f"Bias detection failed: {e}")
        return "neutral"