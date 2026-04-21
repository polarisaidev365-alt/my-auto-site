import os
import json
import feedparser
from datetime import datetime, timedelta
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# 1. Bing News RSS から「今週のAIニュース」を取得
# -----------------------------
RSS_URL = "https://rss.msn.com/en-us/technology"
feed = feedparser.parse(RSS_URL)

print("=== RSS DEBUG ===")
print("entries count:", len(feed.entries))
if len(feed.entries) > 0:
    e = feed.entries[0]
    print("first entry keys:", e.keys())
    print("has published_parsed:", hasattr(e, "published_parsed"))
    print("raw published:", getattr(e, "published", None))
print("=== RSS DEBUG END ===")

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
        "source": entry.link,  # Bing のリンクをそのまま使う
        "published": published.strftime("%Y-%m-%d")
    })

articles = articles[:50]

# -----------------------------
# 2. OpenAI に要約させる（主要ニュース + 詳細ニュース）
# -----------------------------
prompt = """
あなたは厳密なJSON生成AIです。
以下の形式のJSON「のみ」を返してください。説明文や前置きは禁止です。

summary の条件：
- 主要ニュース：自然な要約（200文字以内）
- 詳細ニュース：400文字以内で要点をまとめる

JSON形式：
{
  "main_topic": {
    "title": "",
    "summary": "",
    "source": "",
    "published": ""
  },
  "topics": [
    {
      "title": "",
      "summary": "",
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

# ★★★ OpenAI の返答を必ずログに出す ★★★
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

data["topics"] = ensure_list(data.get("topics", []))
data["details"] = ensure_list(data.get("details", []))

# topics を 5 件に補完
while len(data["topics"]) < 5:
    data["topics"].append({
        "title": "追加トピック",
        "summary": "AI関連の補完ニュースです。",
        "source": "",
        "published": today.strftime("%Y-%m-%d")
    })

# details を 20 件に補完
while len(data["details"]) < 20:
    data["details"].append({
        "title": "追加詳細ニュース",
        "summary": "AI関連の補完ニュースです。（400文字要点）",
        "source": "",
        "published": today.strftime("%Y-%m-%d")
    })

# -----------------------------
# 3. HTML 生成（画像なし）
# -----------------------------
with open("template.html", "r", encoding="utf-8") as f:
    html = f.read()

main = data["main_topic"]
html = html.replace("{{MAIN_TITLE}}", main["title"])
html = html.replace("{{MAIN_SUMMARY}}", main["summary"])
html = html.replace("{{MAIN_SOURCE}}", main["source"])
html = html.replace("{{MAIN_PUBLISHED}}", main["published"])

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

# 詳細ニュース表
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

# 出力
os.makedirs("public", exist_ok=True)
with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html)
