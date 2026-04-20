import os
import json
import feedparser
from datetime import datetime, timedelta
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# 1. Bing News RSS から本物の今日のニュースを取得
# -----------------------------
RSS_URL = "https://www.bing.com/news/search?q=AI&format=rss"

feed = feedparser.parse(RSS_URL)

today = datetime.utcnow()
yesterday = today - timedelta(days=1)

articles = []

for entry in feed.entries:
    # pubDate を datetime に変換
    try:
        published = datetime(*entry.published_parsed[:6])
    except:
        continue

    # 今日〜昨日のニュースだけ採用
    if published < yesterday:
        continue

    articles.append({
        "title": entry.title,
        "summary": entry.summary,
        "link": entry.link,
        "published": published.strftime("%Y-%m-%d"),
    })

# ニュースが少ない場合の保険
articles = articles[:30]  # 最大30件取得


# -----------------------------
# 2. OpenAI に要約させる
# -----------------------------
prompt = """
あなたは厳密なJSON生成AIです。
以下の形式のJSON「のみ」を返してください。説明文や前置きは禁止です。

すべての文章（title, summary）は自然な日本語で書いてください。

入力として、今日のAIニュース記事を渡します。
これをもとに、以下のJSONを生成してください：

{
  "main_topic": {{
    "title": "",
    "summary": "",
    "image_keyword": ""
  }},
  "topics": [
    {{
      "title": "",
      "summary": "",
      "image_keyword": ""
    }}
  ],
  "details": [
    {{
      "title": "",
      "summary": "",
      "image_keyword": "",
      "source": "",
      "published": ""
    }}
  ]
}

条件：
1. main_topic は最も重要なニュース1件
2. topics は主要ニュース5件
3. details は詳細ニュース20件
4. image_keyword は英単語（ai, robotics など）
5. source は記事のリンク
6. published は YYYY-MM-DD 形式

以下が今日のニュース一覧です：

{json.dumps(articles, ensure_ascii=False)}
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

raw = response.choices[0].message.content.strip()

# JSON抽出
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
main_kw = data["main_topic"]["image_keyword"]
html = html.replace("{{MAIN_IMAGE}}", safe_image(main_kw))
html = html.replace("{{MAIN_TITLE}}", data["main_topic"]["title"])
html = html.replace("{{MAIN_SUMMARY}}", data["main_topic"]["summary"])

