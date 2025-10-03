import os
import requests
from dotenv import load_dotenv

load_dotenv()

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
BASE_URL = "https://newsapi.org/v2/top-headlines"

def fetch_top_headlines(country="us", q=None, page_size=10):
    params = {
        "apiKey": NEWSAPI_KEY,
        "country": country,
        "pageSize": page_size
    }
    if q:
        params["q"] = q

    try:
        r = requests.get(BASE_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "ok":
            raise Exception(f"NewsAPI Error: {data.get('message', 'Unknown error')}")
        return data.get("articles", [])
    except requests.exceptions.RequestException as e:
        raise Exception(f"NewsAPI request failed: {str(e)}")
