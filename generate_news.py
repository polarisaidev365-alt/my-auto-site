import os
import json
import feedparser
from datetime import datetime, timedelta
from openai import OpenAI
import re

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# 1. Bing News RSS から「今週のAIニュース」を取得
# -----------------------------
RSS_URL = "https://www.bing.com/news/search?q=AI&format=rss"
feed = feedparser.parse(RSS_URL)

today = datetime.utcnow()
one_week_ago = today - timedelta(days=7)

articles = []
for entry in feed.entries:
    try:
        published = datetime(*entry.published_parsed[:6])
    except:
        continue

    if published < one_week_ago:
        continue

    articles.append({
        "title": entry.title,
        "summary": entry.summary,
        "source": entry.link,
        "published": published.strftime("%Y-%m-%d")
    })

articles = articles[:50]

# -----------------------------
# 2. OpenAI に要約させる（400文字要点＋JSON壊れ防止）
# -----------------------------
prompt = """
あなたは厳密なJSON生成AIです。
以下の形式のJSON「のみ」を返してください。説明文や前置きは禁止です。

summary の条件：
- 主要ニュース：自然な要約
- 詳細ニュース：400文字以内で要点をまとめる

image_keyword の条件：
- 必ず英単語1〜2語（例：ai, robotics）
- 日本語は禁止

JSON形式：
{
  "main_topic": {
    "title": "",
    "summary": "",
    "image_keyword": "",
    "source": "",
    "published": ""
  },
  "topics": [
    {
      "title": "",
      "summary": "",
      "image_keyword": "",
      "source": "",
      "published": ""
    }
  ],
  "details": [
    {
      "title": "",
      "summary": "",
      "source": "",
      "published": ""
    }
  ]
}

条件：
- main_topic は今週の最重要ニュース1件
- topics は今週の主要ニュース5件
- details は今週の詳細ニュース20件
- summary は400文字以内（details）
- 必ず JSON のみを返す
"""

prompt += "\n\n今週のニュース一覧：\n"
prompt += json.dumps(articles, ensure_ascii=False)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

raw = response.choices[0].message.content.strip()

# ★★★ OpenAI の返答を必ずログに出す（これが重要） ★★★
print("=== OPENAI RAW RESPONSE START ===")
print(raw)
print("=== OPENAI RAW RESPONSE END ===")

# JSON抽出
start = raw.find("{")
end = raw.rfind("}") + 1
json_str = raw[start:end]

data = json.loads(json_str)

# -----------------------------
# 2.5 JSON の壊れを修復
# -----------------------------
def ensure_list(v):
    return v if isinstance(v, list) else [v]

def sanitize_keyword(k):
    if not k:
        return "ai"
    k = re.sub(r"[^a-zA-Z ]", "", k)
    if len(k.strip()) == 0:
        return "ai"
    return k.strip()

data["topics"] = ensure_list(data.get("topics", []))
data["details"] = ensure_list(data.get("details", []))

while len(data["topics"]) < 5:
    data["topics"].append({
        "title": "追加トピック",
        "summary": "AI関連の補完ニュースです。",
        "image_keyword": "ai",
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

data["main_topic"]["image_keyword"] = sanitize_keyword(data["main_topic"].get("image_keyword", "ai"))
for t in data["topics"]:
    t["image_keyword"] = sanitize_keyword(t.get("image_keyword", "ai"))

# -----------------------------
# 3. HTML 生成
# -----------------------------
def safe_image(keyword):
    return f"https://source.unsplash.com/featured/?{keyword}"

with open("template.html", "r", encoding="utf-8") as f:
    html = f.read()

main = data["main_topic"]
html = html.replace("{{MAIN_IMAGE}}", safe_image(main["image_keyword"]))
html = html.replace("{{MAIN_TITLE}}", main["title"])
html = html.replace("{{MAIN_SUMMARY}}", main["summary"])

cards = ""
for t in data["topics"][:5]:
    cards += f"""
    <div class="news-card">
      <img src="{safe_image(t['image_keyword'])}" />
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
