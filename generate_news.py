import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

prompt = """
世界の今日のAIニュースを5つの主要トピックに整理してまとめてください。

出力は必ず以下のJSON形式で返してください：

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

各トピックには必ず画像URLを1つ含めてください。
画像URLは著作権的に安全なフリー画像（Unsplashなど）を使用してください。
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    response_format={"type": "json_object"},
    messages=[{"role": "user", "content": prompt}]
)

# 返答は必ず JSON になる
data = response.choices[0].message.parsed

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
