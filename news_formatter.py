import json
import os
import re


INPUT_FILE = "news_unique.json"
OUTPUT_FILE = "news_ready.json"


def load_news():
    if not os.path.exists(INPUT_FILE):
        return []

    try:
        with open(
            INPUT_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return data if isinstance(data, list) else []

    except Exception as error:
        print("Could not load news:")
        print(error)
        return []


def save_news(news):
    with open(
        OUTPUT_FILE,
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

    text = text.replace(
        "\u200c",
        " ",
    )

    text = text.replace(
        "\u200f",
        " ",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def shorten_title(title):
    title = clean_text(title)

    # حذف عبارت‌های تبلیغاتی/تکراری ابتدای عنوان
    prefixes = [
        "آخرین اخبار ",
        "آخرین خبر ",
        "گزارش ",
        "جزئیات ",
        "تصاویر ",
        "ویدئو ",
    ]

    for prefix in prefixes:
        if title.startswith(prefix):
            title = title[len(prefix):].strip()

    # حذف فاصله‌های اضافی
    title = re.sub(
        r"\s+",
        " ",
        title,
    ).strip()

    # کوتاه کردن عنوان‌های خیلی بلند
    if len(title) > 90:
        title = title[:87].rstrip() + "..."

    return title


def split_sentences(text):
    text = clean_text(text)

    if not text:
        return []

    parts = re.split(
        r"(?<=[.!؟])\s+",
        text,
    )

    parts = [
        part.strip()
        for part in parts
        if part.strip()
    ]

    return parts


def build_summary(item):
    summary = clean_text(
        item.get("summary", "")
    )

    title = clean_text(
        item.get("title", "")
    )

    if not summary:
        return (
            title
            if title
            else "اطلاعات تکمیلی در منبع اصلی خبر موجود است."
        )

    sentences = split_sentences(
        summary
    )

    # فقط ۲ تا ۳ جمله نگه می‌داریم
    selected = sentences[:3]

    result = " ".join(
        selected
    ).strip()

    # اگر RSS خلاصه خیلی کوتاه بود،
    # خود عنوان را تکرار نمی‌کنیم.
    if not result:
        result = (
            "جزئیات بیشتر در لینک منبع خبر موجود است."
        )

    return result


def format_news(item):
    title = shorten_title(
        item.get("title", "")
    )

    summary = build_summary(
        item
    )

    source = clean_text(
        item.get("source", "")
    )

    link = clean_text(
        item.get("link", "")
    )

    return {
        "title": title,
        "summary": summary,
        "source": source,
        "link": link,
        "priority": item.get(
            "priority",
            "low",
        ),
        "market_score": item.get(
            "market_score",
            0,
        ),
        "published": item.get(
            "published",
            "",
        ),
        "collected_at": item.get(
            "collected_at",
            "",
        ),
    }


def main():
    print("===================================")
    print("ZarinMah News Formatter")
    print("===================================")

    news = load_news()

    ready_news = []

    for item in news:
        formatted = format_news(
            item
        )

        if not formatted["title"]:
            continue

        if not formatted["link"]:
            continue

        ready_news.append(
            formatted
        )

    save_news(
        ready_news
    )

    print(
        "Input news:",
        len(news),
    )

    print(
        "Ready news:",
        len(ready_news),
    )

    print()
    print("Sample formatted news:")

    for item in ready_news[:5]:
        print()
        print(
            "Title:",
            item["title"],
        )
        print(
            "Summary:",
            item["summary"],
        )
        print(
            "Source:",
            item["source"],
        )
        print(
            "Link:",
            item["link"],
        )


if __name__ == "__main__":
    main()
