import os
import json
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from openai import OpenAI
from urllib.parse import urlparse, parse_qs

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# Google News のリダイレクト URL を実記事 URL に変換
# -----------------------------
def extract_real_url(google_news_url):
    try:
        parsed = urlparse(google_news_url)
        qs = parse_qs(parsed.query)
        if "url" in qs:
            return qs["url"][0]
    except:
        pass
    return google_news_url


# -----------------------------
# Google News 内部リンク → 実記事 URL を取得（GET）
# -----------------------------
def resolve_final_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)

        soup = BeautifulSoup(r.text, "html.parser")

        # og:url を探す（最優先）
        og = soup.find("meta", property="og:url")
        if og and og.get("content"):
            return og["content"]

        # canonical を探す
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            return canonical["href"]

    except Exception as e:
        print("URL resolve error:", e)

    return url  # 取得できなければ元の URL を返す


# -----------------------------
# 1. Google News RSS から AI ニュースを取得
# -----------------------------
RSS_URL = "https://news.google.com/rss/search?q=AI&hl=ja&gl=JP&ceid=JP:ja"

feed = feedparser.parse(RSS_URL)

print("=== RSS DEBUG ===")
print("entries count:", len(feed.entries))
print("=== RSS DEBUG END ===")

today = datetime.utcnow()
one_week_ago = today - timedelta(days=7)

articles = []

for entry in feed.entries:
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

    # Google News → 実記事 URL に変換
    real_url = extract_real_url(entry.link)
    real_url = resolve_final_url(real_url)

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

# JSON 化前に datetime を削除
for a in articles:
    if "published_dt" in a:
        del a["published_dt"]

# 主要ニュース 5 件
main_topics = articles[:5]

# 詳細ニュース 20 件
detail_topics = articles[:20]


# -----------------------------
# 2. OpenAI に要約させる（日本語タイトルに変更）
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
      "source": "",
      "published": ""
    }
  ],
  "details": [
    {
      "title": "（日本語タイトル）",
      "summary": "",
      "source": "",
      "published": ""
    }
  ]
}

条件：
- topics は主要ニュース5件
- details は詳細ニュース20件（過去1週間の新しい順）
- summary は文字数制限を守る
- タイトルは必ず日本語にする
- URL は書き換えず、入力された URL をそのまま返す
- 必ず JSON のみを返す
"""

prompt += "\n\n今週のニュース一覧：\n"
prompt += json.dumps(articles, ensure_ascii=False)

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
# JSON 修復
# -----------------------------
def ensure_list(v):
    return v if isinstance(v, list) else [v]

data["topics"] = ensure_list(data.get("topics", []))
data["details"] = ensure_list(data.get("details", []))

# -----------------------------
# URL を OpenAI の出力からではなく、元の articles から再セット
# -----------------------------
title_to_url = {a["title"]: a["source"] for a in articles}

def fix_url(item):
    if item["title"] in title_to_url:
        item["source"] = title_to_url[item["title"]]
    return item

data["topics"] = [fix_url(t) for t in data["topics"]]
data["details"] = [fix_url(d) for d in data["details"]]

# 不足分補完
while len(data["topics"]) < 5:
    data["topics"].append({
        "title": "追加主要ニュース",
        "summary": "AI関連の補完ニュースです。",
        "source": "",
        "published": today.strftime("%Y-%m-%d")
    })

while len(data["details"]) < 20:
    data["details"].append({
        "title": "追加詳細ニュース",
        "summary": "AI関連の補完ニュースです。（400文字要点）",
        "source": "",
        "published": today.strftime("%Y-%m-%d")
    })


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
