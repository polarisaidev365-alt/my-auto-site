import os
import json
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from openai import OpenAI
from urllib.parse import urlparse, urlunparse

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# MSN / Bing の中間ページ → 実記事 URL を取得
# -----------------------------
def resolve_final_url(url):
    try:
        # クエリパラメータを削除（?ocid=xxx など）
        parsed = urlparse(url)
        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(clean_url, headers=headers, timeout=10)

        soup = BeautifulSoup(r.text, "html.parser")

        # og:url（最優先）
        og = soup.find("meta", property="og:url")
        if og and og.get("content"):
            return og["content"]

        # canonical
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            return canonical["href"]

    except Exception as e:
        print("URL resolve error:", e)

    return url  # 取得できなければ元の URL


# -----------------------------
# 1. Bing News RSS から AI ニュースを取得
# -----------------------------
RSS_URL = "https://www.bing.com/news/search?q=AI&format=rss&cc=JP&setlang=ja-jp"

feed = feedparser.parse(RSS_URL)

print("=== RSS DEBUG ===")
print("entries count:", len(feed.entries))
print("=== RSS DEBUG END ===")

today = datetime.utcnow()
one_week_ago = today - timedelta(days=7)

articles = []
seen = set()  # 重複排除

for entry in feed.entries:
    # 日付の取得（published → updated → today）
    published_dt = None

    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            published_dt = datetime(*entry.published_parsed[:6])
        except:
            published_dt = None

    if published_dt is None and hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            published_dt = datetime(*entry.updated_parsed[:6])
        except:
            published_dt = None

    if published_dt is None:
        published_dt = today

    # Bing RSS の URL（MSN の中間ページ）
    raw_url = entry.link

    # 実記事 URL に変換
    real_url = resolve_final_url(raw_url)

    # 重複排除（タイトル + URL）
    key = entry.title + real_url
    if key in seen:
        continue
    seen.add(key)

    articles.append({
        "title": entry.title,
        "summary": getattr(entry, "summary", ""),
        "source": real_url,
        "published": published_dt.strftime("%Y-%m-%d"),
        "published_dt": published_dt
    })

# -----------------------------
# 新しい順に並べ替え
# -----------------------------
articles.sort(key=lambda x: x["published_dt"], reverse=True)

# datetime を削除
for a in articles:
    del a["published_dt"]

# 20 件確保（足りない場合はそのまま）
main_topics = articles[:5]
detail_topics = articles[:20]


# -----------------------------
# 2. OpenAI に要約させる（URL は渡さない）
# -----------------------------
prompt = """
あなたは厳密なJSON生成AIです。
以下の形式のJSON「のみ」を返してください。説明文は禁止です。

summary の条件：
- 主要ニュース：200文字以内
- 詳細ニュース：400文字以内

JSON形式：
{
  "topics": [
    {
      "title": "（日本語タイトル）",
      "summary": "",
      "published": ""
    }
  ],
  "details": [
    {
      "title": "（日本語タイトル）",
      "summary": "",
      "published": ""
    }
  ]
}

条件：
- topics は主要ニュース5件
- details は詳細ニュース20件
- summary は文字数制限を守る
- タイトルは必ず日本語にする
- URL は返さない（後で付ける）
- 必ず JSON のみを返す
"""

articles_no_url = [
    {"title": a["title"], "summary": a["summary"], "published": a["published"]}
    for a in articles
]

prompt += "\n\n今週のニュース一覧：\n"
prompt += json.dumps(articles_no_url, ensure_ascii=False)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

raw = response.choices[0].message.content.strip()

print("=== OPENAI RAW RESPONSE START ===")
print(raw)
print("=== OPENAI RAW RESPONSE END ===")

# JSON抽出
start = raw.find("{")
end = raw.rfind("}") + 1
json_str = raw[start:end]

data = json.loads(json_str)

# -----------------------------
# URL を index で再セット（OpenAI の URL は信用しない）
# -----------------------------
for i, t in enumerate(data["topics"]):
    t["source"] = main_topics[i]["source"]

for i, d in enumerate(data["details"]):
    d["source"] = detail_topics[i]["source"]


# -----------------------------
# 3. HTML 生成
# -----------------------------
with open("template.html", "r", encoding="utf-8") as f:
    html = f.read()

# 主要ニュースカード
cards = ""
for t in data["topics"][:5]:
    cards += f"""
    <div class="news-card">
      <div class="news-card-content">
        <h3>{t['title']}</h3>
        <p>{t['summary']}</p>
        <div class="news-meta">
          出典: <a href="{t['source']}" target="_blank">{t['source']}</a><br>
          公開日: {t['published']}
        </div>
      </div>
    </div>
    """

html = html.replace("{{NEWS_CARDS}}", cards)

# 詳細ニュース
details_html = ""
for d in data["details"][:20]:
    summary_400 = d["summary"][:400]
    details_html += f"""
    <tr>
      <td>{d['title']}</td>
      <td>{summary_400}</td>
      <td><a href="{d['source']}" target="_blank">{d['source']}</a></td>
      <td>{d['published']}</td>
    </tr>
    """

html = html.replace("{{DETAILS_LIST}}", details_html)

os.makedirs("public", exist_ok=True)
with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html)
