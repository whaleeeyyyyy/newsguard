from transformers import pipeline

# ---- Summarization (smaller model) ----
summarizer = pipeline(
    "summarization",
    model="sshleifer/distilbart-cnn-12-6",
    device=-1  # CPU
)

# ---- Sentiment analysis ----
sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english",
    device=-1
)

# ---- Zero-shot classification for bias detection ----
classifier = pipeline(
    "zero-shot-classification",
    model="sshleifer/distilbart-mnli-12-3",
    device=-1
)

# ---- Helper functions ----
def summarize_text(text):
    try:
        summary = summarizer(text, max_length=130, min_length=30, do_sample=False)
        return summary[0]['summary_text']
    except Exception:
        return None

def analyze_sentiment(text):
    try:
        result = sentiment_analyzer(text)
        return result[0]['label']
    except Exception:
        return None

def classify_text(text, candidate_labels=["left", "center", "right"]):
    try:
        result = classifier(text, candidate_labels)
        return result['labels'][0]
    except Exception:
        return None
