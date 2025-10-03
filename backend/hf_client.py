import os
import requests
from dotenv import load_dotenv
from hashlib import sha256

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# simple in-memory cache
CACHE = {}

def cache_key(task, text, params=None):
    key = f"{task}:{sha256(text.encode()).hexdigest()}"
    if params:
        key += ":" + sha256(str(params).encode()).hexdigest()
    return key

def hf_request(model, payload, task):
    key = cache_key(task, payload.get("inputs", ""), payload.get("parameters"))
    if key in CACHE:
        return CACHE[key]
    url = f"https://api-inference.huggingface.co/models/{model}"
    r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    if r.status_code != 200:
        raise Exception(f"HF API Error {r.status_code}: {r.text}")
    CACHE[key] = r.json()
    return CACHE[key]

def summarize(text):
    return hf_request(
        "facebook/bart-large-cnn",
        {"inputs": text, "parameters": {"max_length": 120, "min_length": 30}},
        task="summarization"
    )[0]["summary_text"]

def sentiment(text):
    return hf_request(
        "distilbert-base-uncased-finetuned-sst-2-english",
        {"inputs": text},
        task="sentiment"
    )[0]["label"]

def bias(text):
    labels = ["left", "center", "right", "neutral"]
    return hf_request(
        "facebook/bart-large-mnli",
        {"inputs": text, "parameters": {"candidate_labels": labels}},
        task="bias"
    )["labels"][0]  # take top label
