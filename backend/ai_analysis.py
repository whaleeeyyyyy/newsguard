# backend/ai_analysis.py
from transformers import pipeline

# --- Load Hugging Face pipelines ---
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
sentiment_analyzer = pipeline("sentiment-analysis")
bias_classifier = pipeline("zero-shot-classification")

# --- Functions ---
def generate_summary(text: str) -> str:
    if not text:
        return ""
    result = summarizer(text, max_length=130, min_length=30, do_sample=False)
    return result[0]["summary_text"]

def get_sentiment(text: str) -> str:
    if not text:
        return "NEUTRAL"
    result = sentiment_analyzer(text)[0]
    return result["label"]

def detect_bias(text: str) -> str:
    if not text:
        return "Unknown"
    candidate_labels = ["Left", "Center", "Right"]
    result = bias_classifier(text, candidate_labels)
    return result["labels"][0]
