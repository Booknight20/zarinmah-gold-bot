import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import feedparser


TEHRAN_TZ = ZoneInfo("Asia/Tehran")

NEWS_FILE = "news_items.json"

NEWS_SOURCES = {
    # =========================
    # منابع ایرانی
    # =========================

    "ایسنا": "https://www.isna.ir/rss",

    "مهر": "https://www.mehrnews.com/rss",

    "تسنیم": (
        "https://www.tasnimnews.com/fa/rss/feed/0/8/0/"
        "مهمترین-اخبار-تسنیم"
    ),

    "دنیای اقتصاد": "https://donya-e-eqtesad.com/feeds/",

    "خبرآنلاین اقتصادی": (
        "https://www.khabaronline.ir/rss/tp/2"
    ),

    "تابناک": "https://www.tabnak.ir/fa/rss/allnews",

    "مشرق": "https://www.mashreghnews.ir/rss",

    # =========================
    # منابع خارجی
    # =========================

    "Kitco": "https://www.kitco.com/news/category/news/rss",

    "Trading Economics": (
        "https://tradingeconomics.com/calendar.rss"
    ),
}


def load_news():
    if not os.path.exists(NEWS_FILE):
        return []

    try:
        with open(
            NEWS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

    except Exception as error:
        print("Could not load existing news:")
        print(error)

    return []


def save_news(news):
    with open(
        NEWS_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            news,
            file,
            ensure_ascii=False,
            indent=2,
        )


def clean_text(text):
    if not text:
        return ""

    return " ".join(
        str(text).split()
    ).strip()


def get_entry_summary(entry):
    summary = entry.get("summary")

    if not summary:
        summary = entry.get("description")

    return clean_text(summary)


def get_entry_published(entry):
    published = (
        entry.get("published")
        or entry.get("updated")
        or ""
    )

    return clean_text(published)


def collect_from_source(source_name, rss_url):
    print()
    print("===================================")
    print("Reading:", source_name)
    print("RSS:", rss_url)

    try:
        feed = feedparser.parse(
            rss_url,
            request_headers={
                "User-Agent": (
                    "ZarinMah-NewsBot/1.0"
                )
            },
        )

    except Exception as error:
        print("RSS read error:", error)
        return []

    if getattr(feed, "bozo", False):
        print(
            "RSS warning:",
            getattr(
                feed,
                "bozo_exception",
                "Unknown RSS error",
            ),
        )

    entries = getattr(
        feed,
        "entries",
        [],
    )

    print("Entries found:", len(entries))

    collected = []

    # برای جلوگیری از ورود تعداد بسیار زیاد خبر
    for entry in entries[:30]:
        title = clean_text(
            entry.get("title")
        )

        link = clean_text(
            entry.get("link")
        )

        if not title or not link:
            continue

        item = {
            "source": source_name,
            "title": title,
            "link": link,
            "summary": get_entry_summary(
                entry
            ),
            "published": get_entry_published(
                entry
            ),
            "collected_at": datetime.now(
                TEHRAN_TZ
            ).isoformat(),
        }

        collected.append(item)

    return collected


def collect_news():
    old_news = load_news()

    existing_links = {
        item.get("link")
        for item in old_news
        if item.get("link")
    }

    new_items = []

    success_count = 0
    failed_count = 0

    for source_name, rss_url in NEWS_SOURCES.items():
        items = collect_from_source(
            source_name,
            rss_url,
        )

        if items:
            success_count += 1
        else:
            failed_count += 1

        for item in items:
            link = item.get("link")

            if not link:
                continue

            if link in existing_links:
                continue

            new_items.append(item)
            existing_links.add(link)

    all_news = old_news + new_items

    # جدیدترین خبرها ابتدا
    all_news.reverse()

    # محدود کردن حجم فایل
    all_news = all_news[:2000]

    save_news(all_news)

    print()
    print("===================================")
    print("Collection finished")
    print("===================================")
    print("Sources:", len(NEWS_SOURCES))
    print("Successful sources:", success_count)
    print("Failed/empty sources:", failed_count)
    print("New news:", len(new_items))
    print("Total saved:", len(all_news))


def main():
    print("===================================")
    print("ZarinMah News Collector")
    print(
        "Tehran time:",
        datetime.now(
            TEHRAN_TZ
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )
    print("===================================")

    collect_news()


if __name__ == "__main__":
    main()
