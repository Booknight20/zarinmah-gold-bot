import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import feedparser


TEHRAN_TZ = ZoneInfo("Asia/Tehran")

NEWS_FILE = "news_items.json"

NEWS_SOURCES = {
    "ایسنا": "https://www.isna.ir/rss",
    "مهر": "https://www.mehrnews.com/rss",
    "تسنیم": "https://www.tasnimnews.com/fa/rss/feed/0/8/0/مهمترین-اخبار-تسنیم",
}


def load_news():
    if not os.path.exists(NEWS_FILE):
        return []

    try:
        with open(NEWS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return []


def save_news(news):
    with open(NEWS_FILE, "w", encoding="utf-8") as file:
        json.dump(
            news,
            file,
            ensure_ascii=False,
            indent=2,
        )


def collect_news():
    news = load_news()

    existing_links = {
        item.get("link")
        for item in news
        if item.get("link")
    }

    new_items = []

    for source_name, rss_url in NEWS_SOURCES.items():
        print()
        print("Reading:", source_name)

        feed = feedparser.parse(rss_url)

        print("Entries found:", len(feed.entries))

        for entry in feed.entries[:20]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                continue

            if link in existing_links:
                continue

            item = {
                "source": source_name,
                "title": title,
                "link": link,
                "collected_at": datetime.now(
                    TEHRAN_TZ
                ).isoformat(),
            }

            new_items.append(item)
            existing_links.add(link)

    news.extend(new_items)

    save_news(news)

    print()
    print("New news items:", len(new_items))
    print("Total saved news:", len(news))


def main():
    print("===================================")
    print("ZarinMah News Collector")
    print(
        "Tehran time:",
        datetime.now(TEHRAN_TZ).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )
    print("===================================")

    collect_news()


if __name__ == "__main__":
    main()
