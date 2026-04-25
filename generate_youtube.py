import os
import requests
from urllib.parse import quote

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Aカテゴリ：AIツール使い方・チュートリアル
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

# Bカテゴリ：AIニュース・技術解説
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


def youtube_search(query):
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&type=video&maxResults=20&q={quote(query)}&key={YOUTUBE_API_KEY}"
    )
    r = requests.get(url)
    return r.json().get("items", [])


def get_video_stats(video_ids):
    if not video_ids:
        return []
    ids = ",".join(video_ids)
    url = (
        "https://www.googleapis.com/youtube/v3/videos"
        f"?part=statistics,snippet&id={ids}&key={YOUTUBE_API_KEY}"
    )
    r = requests.get(url)
    return r.json().get("items", [])


def score_video(stats):
    view = int(stats["statistics"].get("viewCount", 0))
    like = int(stats["statistics"].get("likeCount", 0))
    return view * 0.7 + like * 3


def filter_items(items, keywords):
    filtered = []
    for it in items:
        title = it["snippet"]["title"]
        desc = it["snippet"].get("description", "")
        if any(k in title or k in desc for k in keywords):
            filtered.append(it)
    return filtered


def build_html(a_videos, b_videos):
    with open("youtube_template.html", "r", encoding="utf-8") as f:
        template = f.read()

    def build_cards(videos):
        cards = ""
        for v in videos:
            cards += f"""
            <div class="yt-card">
                <h3>{v['title']}</h3>
                <iframe width="560" height="315"
                    src="https://www.youtube.com/embed/{v['id']}"
                    frameborder="0" allowfullscreen></iframe>
                <p>再生数: {v['views']:,}　高評価: {v['likes']:,}</p>

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

    html = template.replace("{{A_SECTION}}", build_cards(a_videos))
    html = html.replace("{{B_SECTION}}", build_cards(b_videos))

    os.makedirs("public", exist_ok=True)
    with open("public/youtube.html", "w", encoding="utf-8") as f:
        f.write(html)


def process_category(queries, filter_words, limit=10):
    all_items = []
    for q in queries:
        items = youtube_search(q)
        filtered = filter_items(items, filter_words)
        for it in filtered:
            all_items.append(it)

    video_ids = [v["id"]["videoId"] for v in all_items][:50]
    stats = get_video_stats(video_ids)

    scored = []
    for s in stats:
        scored.append({
            "id": s["id"],
            "title": s["snippet"]["title"],
            "views": int(s["statistics"].get("viewCount", 0)),
            "likes": int(s["statistics"].get("likeCount", 0)),
            "score": score_video(s)
        })

    return sorted(scored, key=lambda x: x["score"], reverse=True)[:limit]


def main():
    a_videos = process_category(A_QUERIES, A_FILTER, 10)
    b_videos = process_category(B_QUERIES, B_FILTER, 10)
    build_html(a_videos, b_videos)


if __name__ == "__main__":
    main()
