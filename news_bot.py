import json
import os
import re
from difflib import SequenceMatcher
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

    text = str(text)

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = text.replace("\u200c", " ")
    text = text.replace("\u200f", " ")
    text = text.replace("\ufeff", " ")

    return " ".join(
        text.split()
    ).strip()


def normalize_title(title):
    title = clean_text(title)

    title = title.replace("ي", "ی")
    title = title.replace("ى", "ی")
    title = title.replace("ك", "ک")
    title = title.replace("ۀ", "ه")
    title = title.replace("ة", "ه")

    title = re.sub(
        r"[«»“”\"'`،؛:,.!?؟()\[\]{}<>/\\|*_+=~\-–—]",
        " ",
        title,
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip().lower()


def title_tokens(title):
    normalized = normalize_title(title)

    tokens = normalized.split()

    # چند کلمه عمومی که ارزش تشخیص خبر ندارند
    common_words = {
        "امروز",
        "جدید",
        "آخرین",
        "گزارش",
        "جزئیات",
        "اعلام",
        "خبر",
        "مهم",
        "تازه",
        "شد",
        "شدند",
        "کرد",
        "کردند",
        "است",
        "هست",
        "به",
        "از",
        "در",
        "با",
        "برای",
        "این",
        "آن",
        "یک",
    }

    return {
        token
        for token in tokens
        if token not in common_words
        and len(token) > 1
    }


def titles_are_duplicate(title1, title2):
    normalized1 = normalize_title(title1)
    normalized2 = normalize_title(title2)

    if not normalized1 or not normalized2:
        return False

    # یکسان بودن دقیق عنوان
    if normalized1 == normalized2:
        return True

    tokens1 = title_tokens(title1)
    tokens2 = title_tokens(title2)

    if not tokens1 or not tokens2:
        return False

    intersection = tokens1 & tokens2
    union = tokens1 | tokens2

    token_similarity = (
        len(intersection) / len(union)
        if union
        else 0
    )

    text_similarity = SequenceMatcher(
        None,
        normalized1,
        normalized2,
    ).ratio()

    # خبرهای تقریباً یکسان
    if text_similarity >= 0.92:
        return True

    # عنوان‌هایی با تفاوت جزئی بین رسانه‌ها
    if (
        text_similarity >= 0.84
        and token_similarity >= 0.72
    ):
        return True

    return False


def is_duplicate(item, existing_items):
    link = clean_text(
        item.get("link")
    )

    title = clean_text(
        item.get("title")
    )

    # ابتدا لینک
    for old_item in existing_items:
        old_link = clean_text(
            old_item.get("link")
        )

        if (
            link
            and old_link
            and link == old_link
        ):
            return True

    # بعد عنوان
    for old_item in existing_items:
        old_title = clean_text(
            old_item.get("title")
        )

        if titles_are_duplicate(
            title,
            old_title,
        ):
            return True

    return False


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


def collect_from_source(
    source_name,
    rss_url,
):
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

    print(
        "Entries found:",
        len(entries),
    )

    collected = []

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

    # ابتدا خود دیتای قبلی را هم پاک‌سازی می‌کنیم
    unique_news = []

    for item in old_news:
        if is_duplicate(
            item,
            unique_news,
        ):
            continue

        unique_news.append(item)

    existing_before = len(unique_news)

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

            if is_duplicate(
                item,
                unique_news,
            ):
                continue

            unique_news.append(item)
            new_items.append(item)

    # جدیدترین خبرها اول
    unique_news.sort(
        key=lambda item: item.get(
            "collected_at",
            "",
        ),
        reverse=True,
    )

    # حجم فایل
    unique_news = unique_news[:2000]

    save_news(unique_news)

    duplicates_removed = (
        existing_before
        + sum(
            1
            for _ in new_items
        )
        - len(unique_news)
    )

    print()
    print("===================================")
    print("Collection finished")
    print("===================================")
    print(
        "Sources:",
        len(NEWS_SOURCES),
    )
    print(
        "Successful sources:",
        success_count,
    )
    print(
        "Failed/empty sources:",
        failed_count,
    )
    print(
        "New unique news:",
        len(new_items),
    )
    print(
        "Total unique saved:",
        len(unique_news),
    )


def main():
    print(
        "==================================="
    )
    print(
        "ZarinMah News Collector"
    )
    print(
        "Tehran time:",
        datetime.now(
            TEHRAN_TZ
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )
    print(
        "==================================="
    )

    collect_news()


if __name__ == "__main__":
    main()
