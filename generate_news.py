import os
import json
import feedparser
from datetime import datetime, timedelta
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# 1. Google News RSS から AI ニュースを取得
# -----------------------------
RSS_URL = "https://news.google.com/rss/search?q=AI&hl=en-US&gl=US&ceid=US:en"

feed = feedparser.parse(RSS_URL)

print("=== RSS DEBUG ===")
print("entries count:", len(feed.entries))
print("=== RSS DEBUG END ===")

today = datetime.utcnow()
one_week_ago = today - timedelta(days=7)

articles = []
for entry in feed.entries:
    # Google News RSS は published_parsed が存在する
    published_dt = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            published_dt = datetime(*entry.published_parsed[:6])
        except:
            published_dt = None

    if published_dt is None:
        published_dt = today

    if published_dt < one_week_ago:
        continue

    articles.append({
        "title": entry.title,
        "summary": getattr(entry
