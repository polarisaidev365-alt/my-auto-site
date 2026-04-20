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
  ]
}

タスク：
世界の今日のAIニュースを5つの主要トピックに整理してまとめてください。

各トピックには必ず画像キーワードを1つ含めてください。
画像キーワードは英単語で、ニュース内容に関連する単語にしてください。
例：ai, robotics, machine-learning, neural-network
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

raw = response.choices[0].message.content.strip()

# JSON抽出（{ 〜 } の範囲を取り出す）
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

# ニュースカード生成
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

# 出力
os.makedirs("public", exist_ok=True)
with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html)
