import os
import json
import feedparser
from datetime import datetime, timedelta
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# 1. Bing News RSS から今日のニュース取得
# -----------------------------
RSS_URL = "https://www.bing.com/news/search?q=AI&format=rss"
feed = feedparser.parse(RSS_URL)

today = datetime.utcnow()
yesterday = today - timedelta(days=1)

articles = []
for entry in feed.entries:
    try:
        published = datetime(*entry.published_parsed[:6])
    except:
        continue

    if published < yesterday:
        continue

    articles.append({
        "title": entry.title,
        "summary": entry.summary,
        "link": entry.link,
        "published": published.strftime("%Y-%m-%d")
    })

articles = articles[:30]  # 最大30件


# -----------------------------
# 2. OpenAI に要約させる（JSON壊れ防止）
# -----------------------------
prompt = """
あなたは厳密なJSON生成AIです。
以下の形式のJSON「のみ」を返してください。説明文や前置きは禁止です。

すべての文章（title, summary）は自然な日本語で書いてください。

JSON形式：
{
  "main_topic": {
    "title": "",
    "summary": "",
    "image_keyword": ""
  },
  "topics": [
    {
      "title": "",
      "summary": "",
      "image_keyword": ""
    }
  ],
  "details": [
    {
      "title": "",
      "summary": "",
      "image_keyword": "",
      "source": "",
      "published": ""
    }
  ]
}

条件：
- main_topic は最重要ニュース1件
- topics は主要ニュース5件
- details は詳細ニュース20件
- image_keyword は英単語（ai, robotics など）
- source は記事のリンク
- published は YYYY-MM-DD 形式
- 必ず JSON のみを返す
"""

prompt += "\n\n今日のニュース一覧：\n"
prompt += json.dumps(articles, ensure_ascii=False)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

raw = response.choices[0].message.content.strip()

# JSON抽出（最初の { から最後の } まで）
start = raw.find("{")
end = raw.rfind("}") + 1
json_str = raw[start:end]

data = json.loads(json_str)


# -----------------------------
# 3. HTML 生成
# -----------------------------
def safe_image(keyword):
    return f"https://source.unsplash.com/featured/?{keyword}"

with open("template.html", "r", encoding="utf-8") as f:
    html = f.read()

# メイントピック
main = data["main_topic"]
html = html.replace("{{MAIN_IMAGE}}", safe_image(main["image_keyword"]))
html = html.replace("{{MAIN_TITLE}}", main["title"])
html = html.replace("{{MAIN_SUMMARY}}", main["summary"])

# 主要5件
cards = ""
for t in data["topics"][:5]:
    cards += f"""
    <div class="news-card">
      <img src="{safe_image(t['image_keyword'])}" />
      <div class="news-card-content">
        <h3>{t['title']}</h3>
        <p>{t['summary']}</p>
      </div>
    </div>
    """
html = html.replace("{{NEWS_CARDS}}", cards)

# 詳細20件
details_html = ""
for d in data["details"][:20]:
    details_html += f"""
    <div class="detail-item">
      <img src="{safe_image(d['image_keyword'])}" />
      <div class="detail-content">
        <h3>{d['title']}</h3>
        <p>{d['summary']}</p>
        <div class="detail-meta">
          出典: <a href="{d['source']}" target="_blank">{d['source']}</a> / 公開日: {d['published']}
        </div>
      </div>
    </div>
    """
html = html.replace("{{DETAILS_LIST}}", details_html)

# 出力
os.makedirs("public", exist_ok=True)
with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html)
