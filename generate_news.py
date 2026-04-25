import os
import json
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from openai import OpenAI
from urllib.parse import urlparse, urlunparse, quote

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# MSN / Bing の中間ページ → 実記事 URL を抽出
# -----------------------------
def resolve_final_url(url):
    try:
        parsed = urlparse(url)
        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(clean_url, headers=headers, timeout=10)

        soup = BeautifulSoup(r.text, "html.parser")

        og = soup.find("meta", property="og:url")
        if og and og.get("content"):
            return og["content"]

        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            return canonical["href"]

    except Exception as e:
        print("URL resolve error:", e)

    return url


# -----------------------------
# 複数 Bing News RSS（日本語ニュース優先）
# -----------------------------
QUERIES = ["AI", "AI 最新", "AI 技術", "人工知能", "生成AI"]

def build_rss_url(query: str) -> str:
    q = quote(query)
    return f"https://www.bing.com/news/search?q={q}&format=rss&cc=JP&setlang=ja-jp"

today = datetime.utcnow()
articles = []
seen = set()

for q in QUERIES:
    rss_url = build_rss_url(q)
    feed = feedparser.parse(rss_url)

    print(f"=== RSS DEBUG ({q}) ===")
    print("entries count:", len(feed.entries))
    print("=== RSS DEBUG END ===")

    for entry in feed.entries:
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

        real_url = resolve_final_url(entry.link)

        key = (entry.title, real_url)
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

for a in articles:
    del a["published_dt"]

main_topics = articles[:5]
detail_topics = articles[:20]

# -----------------------------
# OpenAI に要約させる
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
      "title": "",
      "summary": "",
      "published": ""
    }
  ],
  "details": [
    {
      "title": "",
      "summary": "",
      "published": ""
    }
  ]
}

条件：
- topics は主要ニュース5件「ちょうど5件」
- details は詳細ニュース20件「ちょうど20件」
- topics と details は必ず別のニュースにする（重複禁止）
- summary は文字数制限を守る
- タイトルは必ず日本語にする
- URL は返さない（後で付ける）
- 必ず JSON のみを返す
"""

articles_no_url = [
    {"title": a["title"], "summary": a["summary"], "published": a["published"]}
    for a in articles
]

prompt += "\n\nニュース一覧：\n"
prompt += json.dumps(articles_no_url, ensure_ascii=False)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

raw = response.choices[0].message.content.strip()

print("=== OPENAI RAW RESPONSE START ===")
print(raw)
print("=== OPENAI RAW RESPONSE END ===")

# JSON抽出（壊れていても復旧）
start = raw.find("{")
end = raw.rfind("}") + 1
json_str = raw[start:end]

try:
    data = json.loads(json_str)
except:
    print("JSON parse error. Using fallback.")
    data = {"topics": [], "details": []}

def ensure_list(v):
    return v if isinstance(v, list) else [v]

data["topics"] = ensure_list(data.get("topics", []))
data["details"] = ensure_list(data.get("details", []))

# -----------------------------
# URL を index で再セット（source が無くてもOK）
# -----------------------------
for i, t in enumerate(data["topics"]):
    if i < len(main_topics):
        t["source"] = main_topics[i].get("source")
        t["published"] = t.get("published") or main_topics[i]["published"]

for i, d in enumerate(data["details"]):
    if i < len(detail_topics):
        d["source"] = detail_topics[i].get("source")
        d["published"] = d.get("published") or detail_topics[i]["published"]

data["topics"] = data["topics"][:5]
data["details"] = data["details"][:20]

# -----------------------------
# HTML 生成
# -----------------------------
with open("template.html", "r", encoding="utf-8") as f:
    template = f.read()

# 主要ニュース
news_cards_html = ""
for t in data["topics"]:
    source = t.get("source")
    source_html = f'出典: <a href="{source}" target="_blank">リンク</a><br>' if source else ""

    news_cards_html += f"""
    <div class="news-card">
      <h3>{t['title']}</h3>
      <p>{t['summary']}</p>
      <div class="news-meta">
        {source_html}
        公開日: {t['published']}
      </div>
    </div>
    """

# 詳細ニュース
details_html = ""
for d in data["details"]:
    source = d.get("source")
    link_html = f'<a href="{source}" target="_blank">リンク</a>' if source else "なし"
    summary_400 = d["summary"][:400]

    details_html += f"""
    <tr>
      <td>{d['title']}</td>
      <td>{summary_400}</td>
      <td>{link_html}</td>
      <td>{d['published']}</td>
    </tr>
    """

html = template.replace("{{NEWS_CARDS}}", news_cards_html)
html = html.replace("{{DETAILS_LIST}}", details_html)

# 出力
os.makedirs("public", exist_ok=True)
with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html)
