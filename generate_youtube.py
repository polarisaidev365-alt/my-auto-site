import os
import requests
import json
from datetime import datetime
from urllib.parse import quote

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

SEARCH_QUERIES = [
    "AI",
    "人工知能",
    "生成AI",
    "AI ツール",
    "AI 解説",
]

def youtube_search(query):
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&type=video&maxResults=20&q={quote(query)}&key={YOUTUBE_API_KEY}"
    )
    r = requests.get(url)
    return r.json().get("items", [])

def get_video_stats(video_ids):
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

def build_html(videos):
    with open("youtube_template.html", "r", encoding="utf-8") as f:
        template = f.read()

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

    html = template.replace("{{YOUTUBE_CARDS}}", cards)

    os.makedirs("public", exist_ok=True)
    with open("public/youtube.html", "w", encoding="utf-8") as f:
        f.write(html)

def main():
    all_results = []
    for q in SEARCH_QUERIES:
        items = youtube_search(q)
        for it in items:
            vid = it["id"]["videoId"]
            title = it["snippet"]["title"]
            all_results.append({"id": vid, "title": title})

    video_ids = [v["id"] for v in all_results][:50]
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

    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)[:10]
    build_html(ranked)

if __name__ == "__main__":
    main()
