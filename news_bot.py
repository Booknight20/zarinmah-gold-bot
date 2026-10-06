import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import feedparser


TEHRAN_TZ = ZoneInfo("Asia/Tehran")

NEWS_FILE = "news_items.json"


NEWS_SOURCES = {
    "تسنیم": "",
    "ایرنا": "",
    "ایسنا": "",
    "دنیای اقتصاد": "",
    "اقتصادنیوز": "",
    "مهر": "",
    "ایلنا": "",
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

    news = load_news()

    print("Saved news items:", len(news))
    print("News sources:", len(NEWS_SOURCES))

    print()
    print("News collector is ready.")
    print("No Telegram message will be sent.")


if __name__ == "__main__":
    main()
