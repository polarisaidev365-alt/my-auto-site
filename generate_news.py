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
    "image_url": ""
  },
  "topics": [
    {
      "title": "",
      "summary": "",
      "image_url": ""
    }
  ]
}

タスク：
世界の今日のAIニュースを5つの主要トピックに整理してまとめてください。
各トピックには必ず著作権的に安全な画像URL（Unsplashなど）を1つ含めてください。
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

raw = response.choices[0].message.content.strip()

# JSON以外の文字が混ざる可能性があるため、最初の { から最後の } までを抽出
start = raw.find("{")
end = raw.rfind("}") + 1
json_str = raw[start:end]

data = json.loads(json_str)

# HTMLテンプレート読み込み
with open("template.html", "r", encoding="utf-8") as f:
    html = f.read()

# メイントピック埋め込み
html = html.replace("{{MAIN_IMAGE}}", data["main_topic"]["image_url"])
html = html.replace("{{MAIN_TITLE}}", data["main_topic"]["title"])
html = html.replace("{{MAIN_SUMMARY}}", data["main_topic"]["summary"])

# ニュースカード生成
cards = ""
for t in data["topics"]:
    card = f"""
    <div class="news-card">
      <img src="{t['image_url']}" />
      <div class="news-card-content">
        <h3>{t['title']}</h3>
        <p>{t['summary']}</p>
      </div>
    </div>
    """
    cards += card

html = html.replace("{{NEWS_CARDS}}", cards)

# 出力
os.makedirs("public", exist_ok=True)
with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html)
