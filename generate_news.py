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
detail_topics = articles[:20]  # 実記事のみ


# -----------------------------
# OpenAI に要約させる（URL は渡さない）
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

start = raw.find("{")
end = raw.rfind("}") + 1
json_str = raw[start:end]

data = json.loads(json_str)

def ensure_list(v):
    return v if isinstance(v, list) else [v]

data["topics"] = ensure_list(data.get("topics", []))
data["details"] = ensure_list(data.get("details", []))

# -----------------------------
# URL を index で再セット
# -----------------------------
for i, t in enumerate(data["topics"]):
    if i < len(main_topics):
        t["source"] = main_topics[i]["source"]
        if not t.get("published"):
            t["published"] = main_topics[i]["published"]

for i, d in enumerate(data["details"]):
    if i < len(detail_topics):
        d["source"] = detail_topics[i]["source"]
        if not d.get("published"):
            d["published"] = detail_topics[i]["published"]

# details は実記事の数に合わせて切る
data["details"] = data["details"][:len(detail_topics)]

# -----------------------------
# 楽天関連商品自動生成（AI × 楽天検索リンク）
# -----------------------------

def generate_rakuten_search_link(keyword):
    """楽天検索リンクを生成（あなたのA8 ID入り）"""
    base = "https://search.rakuten.co.jp/search/mall/"
    encoded = urllib.parse.quote(keyword)
    return f"{base}{encoded}/?scid=af_pc_etc&aid=a26042506136"


def generate_related_products(news_title, summary):
    """AIに関連商品名を3つ生成させ、楽天検索リンクに変換"""
    prompt = f"""
以下のニュース内容に関連する商品を3つ提案してください。
商品名のみを箇条書きで返してください。

ニュースタイトル: {news_title}
概要: {summary}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    raw_text = response.choices[0].message.content.strip()
    product_names = [p.replace("-", "").strip() for p in raw_text.split("\n") if p.strip()]

    # 楽天検索リンクに変換
    product_links = []
    for name in product_names:
        link = generate_rakuten_search_link(name)
        product_links.append((name, link))

    return product_links


def build_related_products_html(product_links):
    """関連商品HTMLを生成"""
    html = '<div class="affiliate-box"><h3>関連商品（楽天）</h3><ul>'
    for name, link in product_links:
        html += f'<li><a href="{link}" target="_blank">{name}</a></li>'
    html += '</ul></div>'
    return html



# -----------------------------
# HTML 生成
# -----------------------------
with open("template.html", "r", encoding="utf-8") as f:
    html = f.read()

cards = ""
for i, t in enumerate(data["topics"][:len(main_topics)]):
    cards += f"""
    <div class="news-card">
      <div class="news-card-content">
        <h3>{t['title']}</h3>
        <p>{t['summary']}</p>
        <div class="news-meta">
          出典: <a href="{t['source']}" target="_blank">リンク</a><br>
          公開日: {t['published']}
        </div>
      </div>
    </div>
    """

html = html.replace("{{NEWS_CARDS}}", cards)

details_html = ""
for d in data["details"]:
    summary_400 = d["summary"][:400]
    details_html += f"""
    <tr>
      <td>{d['title']}</td>
      <td>{summary_400}</td>
      <td><a href="{d['source']}" target="_blank">リンク</a></td>
      <td>{d['published']}</td>
    </tr>
    """

html = html.replace("{{DETAILS_LIST}}", details_html)

# 楽天バナー（234x60）をテーブル下に挿入
rakuten_banner = """
<div style="margin: 20px 0; text-align: center;">
<a href="https://rpx.a8.net/svt/ejp?a8mat=4B1THV+7Q1GAA+2HOM+6TMLD&rakuten=y&a8ejpredirect=http%3A%2F%2Fhb.afl.rakuten.co.jp%2Fhgc%2F0eac8dc2.9a477d4e.0eac8dc3.0aa56a48%2Fa26042506136_4B1THV_7Q1GAA_2HOM_6TMLD%3Fpc%3Dhttp%253A%252F%252Fbooks.rakuten.co.jp%252F%26m%3Dhttp%253A%252F%252Fbooks.rakuten.co.jp%252F" rel="nofollow">
<img src="http://hbb.afl.rakuten.co.jp/hsb/0eb46e44.85d79ba9.0eb46e39.39a610d9/" border="0"></a>
<img border="0" width="1" height="1" src="https://www19.a8.net/0.gif?a8mat=4B1THV+7Q1GAA+2HOM+6TMLD" alt="">
</div>
"""

html = html.replace("{{RAKUTEN_BANNER}}", rakuten_banner)

os.makedirs("public", exist_ok=True)
with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html)
