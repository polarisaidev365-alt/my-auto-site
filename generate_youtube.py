import os
import requests
from urllib.parse import quote
import json

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# -----------------------------
# カテゴリ定義
# -----------------------------
A_QUERIES = [
    "AI 使い方",
    "AI ツール 使い方",
    "ChatGPT 使い方",
    "生成AI チュートリアル",
    "AI 自動化",
    "AI ワークフロー",
    "Midjourney 使い方",
    "Runway 使い方",
]

A_FILTER = ["使い方", "解説", "講座", "チュートリアル", "初心者", "入門", "How to", "Tutorial"]

B_QUERIES = [
    "AI ニュース",
    "AI 最新",
    "AI 解説",
    "AI 技術",
    "AI 動向",
    "AI 研究",
    "生成AI ニュース",
]

B_FILTER = ["ニュース", "最新", "解説", "動向", "研究", "速報"]


# -----------------------------
# YouTube API ラッパー（安全版）
# -----------------------------
def youtube_search(query):
    try:
        url = (
            "https://www.googleapis.com/youtube/v3/search"
            f"?part=snippet&type=video&maxResults=20&q={quote(query)}&key={YOUTUBE_API_KEY}"
        )
        r = requests.get(url, timeout=10)
        data = r.json()
        return data.get("items", [])
    except Exception as e:
        print("search error:", e)
        return []


def get_video_stats(video_ids):
    if not video_ids:
        return []

    try:
        ids = ",".join(video_ids)
        url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=statistics,snippet&id={ids}&key={YOUTUBE_API_KEY}"
        )
        r = requests.get(url, timeout=10)
        data = r.json()
        return data.get("items", [])
    except Exception as e:
        print("stats error:", e)
        return []


# -----------------------------
# スコア計算（安全版）
# -----------------------------
def score_video(stats):
    try:
        view = int(stats["statistics"].get("viewCount", 0))
        like = int(stats["statistics"].get("likeCount", 0))
        return view * 0.7 + like * 3
    except:
        return 0


# -----------------------------
# フィルタリング
# -----------------------------
def filter_items(items, keywords):
    filtered = []
    for it in items:
        try:
            title = it["snippet"]["title"]
            desc = it["snippet"].get("description", "")
            if any(k in title or k in desc for k in keywords):
                filtered.append(it)
        except:
            continue
    return filtered


# -----------------------------
# HTML カード生成
# -----------------------------
def build_cards(videos):
    cards = ""
    for v in videos:
        vid = v.get("id")
        title = v.get("title", "タイトル不明")
        views = v.get("views", 0)
        likes = v.get("likes", 0)

        cards += f"""
        <div class="yt-card">
            <h3>{title}</h3>
            <iframe width="560" height="315"
                src="https://www.youtube.com/embed/{vid}"
                frameborder="0" allowfullscreen></iframe>
            <p>再生数: {views:,}　高評価: {likes:,}</p>

            <div class="affiliate-box">
                <h4>関連商品（楽天）</h4>
                <ul>
                    <li><a href="https://search.rakuten.co.jp/search/mall/AI本/?scid=af_pc_etc&aid=a26042506136" target="_blank">AI本</a></li>
                    <li><a href="https://search.rakuten.co.jp/search/mall/マイク/?scid=af_pc_etc&aid=a26042506136" target="_blank">マイク</a></li>
                    <li><a href="https://search.rakuten.co.jp/search/mall/Webカメラ/?scid=af_pc_etc&aid=a26042506136" target="_blank">Webカメラ</a></li>
                </ul>
            </div>
        </div>
        """
    return cards


# -----------------------------
# カテゴリ処理（安全版）
# -----------------------------
def process_category(queries, filter_words, limit=10):
    all_items = []

    # 検索
    for q in queries:
        items = youtube_search(q)
        filtered = filter_items(items, filter_words)
        all_items.extend(filtered)

    # videoId 抽出（安全）
    video_ids = []
    for v in all_items:
        try:
            vid = v["id"]["videoId"]
            video_ids.append(vid)
        except:
            continue

    video_ids = video_ids[:50]

    # 統計取得
    stats = get_video_stats(video_ids)

    scored = []
    for s in stats:
        try:
            scored.append({
                "id": s["id"],
                "title": s["snippet"]["title"],
                "views": int(s["statistics"].get("viewCount", 0)),
                "likes": int(s["statistics"].get("likeCount", 0)),
                "score": score_video(s)
            })
        except:
            continue

    # スコア順
    scored.sort(key=lambda x: x["score"], reverse=True)

    # 足りない場合は空データで補完
    while len(scored) < limit:
        scored.append({
            "id": "",
            "title": "データなし",
            "views": 0,
            "likes": 0,
            "score": 0
        })

    return scored[:limit]


# -----------------------------
# メイン処理
# -----------------------------
def main():
    # Aカテゴリ
    a_videos = process_category(A_QUERIES, A_FILTER, 10)

    # Bカテゴリ
    b_videos = process_category(B_QUERIES, B_FILTER, 10)

    # テンプレート読み込み
    try:
        with open("youtube_template.html", "r", encoding="utf-8") as f:
            template = f.read()
    except:
        print("template missing. creating fallback.")
        template = """
        <html><body>
        <h2>AIツールの使い方・チュートリアル</h2>
        {{A_SECTION}}
        <h2>AIニュース・技術解説</h2>
        {{B_SECTION}}
        </body></html>
        """

    html = template.replace("{{A_SECTION}}", build_cards(a_videos))
    html = html.replace("{{B_SECTION}}", build_cards(b_videos))

    os.makedirs("public", exist_ok=True)
    with open("public/youtube.html", "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
