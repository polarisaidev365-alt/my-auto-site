import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

prompt = """
あなたは厳密なJSON生成AIです。
以下の形式のJSON「のみ」を返してください。説明文や前置きは禁止です。

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

タスク：
1. 世界の今日のAIニュースを5つの主要トピックに整理してまとめてください。
2. さらに、AIに関する詳細ニュースを20件生成してください。
3. 画像キーワードは英単語で、ニュース内容に関連する単語にしてください。
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

# 画像URLを安定生成する関数
def safe_image(keyword):
    return f"https://source.unsplash.com/featured/?{keyword}"

# HTMLテンプレート読み込み
with open("template.html", "r", encoding="utf-8") as f:
    html = f.read()

# メイントピック埋め込み
main_kw = data["main_topic"]["image_keyword"]
html = html.replace("{{MAIN_IMAGE}}", safe_image(main_kw))
html = html.replace("{{MAIN_TITLE}}", data["main_topic"]["title"])
html = html.replace("{{MAIN_SUMMARY}}", data["main_topic"]["summary"])

# 主要トピックカード生成
cards = ""
for t in data["topics"]:
    kw = t["image_keyword"]
    img = safe_image(kw)
    card = f"""
    <div class="news-card">
      <img src="{img}" />
      <div class="news-card-content">
        <h3>{t['title']}</h3>
        <p>{t['summary']}</p>
      </div>
    </div>
    """
    cards += card

html = html.replace("{{NEWS_CARDS}}", cards)

# 詳細ニュース20件生成
details_html = ""
for d in data["details"]:
    kw = d["image_keyword"]
    img = safe_image(kw)
    block = f"""
    <div class="detail-item">
      <img src="{img}" />
      <div class="detail-content">
        <h3>{d['title']}</h3>
        <p>{d['summary']}</p>
        <div class="detail-meta">
          出典: {d['source']} / 公開日: {d['published']}
        </div>
      </div>
    </div>
    """
    details_html += block

html = html.replace("{{DETAILS_LIST}}", details_html)

# 出力
os.makedirs("public", exist_ok=True)
with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html)
