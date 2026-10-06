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

    text = text.replace(
        "\ufeff",
        " ",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def normalize_title(title):
    title = clean_text(title)

    # حذف عبارت‌های زائد ابتدای تیتر
    prefixes = [
        "گزارش ",
        "جزئیات ",
        "آخرین اخبار ",
        "آخرین خبر ",
        "تصاویر ",
        "ویدئو ",
        "طبق اعلام ",
    ]

    for prefix in prefixes:
        if title.startswith(prefix):
            title = title[
                len(prefix):
            ].strip()

    # حذف فاصله‌های چندگانه
    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    # محدود کردن طول تیتر
    if len(title) > 100:
        title = (
            title[:97].rstrip()
            + "..."
        )

    return title


def split_sentences(text):
    text = clean_text(text)

    if not text:
        return []

    # جدا کردن جمله‌های فارسی و انگلیسی
    parts = re.split(
        r"(?<=[.!؟])\s+",
        text,
    )

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


def remove_redundant_opening(text):
    """
    فقط عبارت‌های خبری تکراری را حذف می‌کند.
    اطلاعات اصلی خبر دست‌نخورده باقی می‌ماند.
    """

    patterns = [
        r"^طبق اعلام[^،:؛]*[،:؛]\s*",
        r"^به گزارش[^،:؛]*[،:؛]\s*",
        r"^براساس اعلام[^،:؛]*[،:؛]\s*",
        r"^بر اساس اعلام[^،:؛]*[،:؛]\s*",
        r"^بررسی‌ها نشان می‌دهد[،:؛]\s*",
    ]

    for pattern in patterns:
        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE,
        )

    return text.strip()


def build_summary(item):
    raw_summary = clean_text(
        item.get("summary", "")
    )

    if not raw_summary:
        return (
            "جزئیات بیشتر در منبع اصلی خبر "
            "در دسترس است."
        )

    summary = remove_redundant_opening(
        raw_summary
    )

    sentences = split_sentences(
        summary
    )

    # حداکثر ۳ جمله
    selected = sentences[:3]

    if selected:
        summary = " ".join(
            selected
        ).strip()
    else:
        summary = clean_text(
            summary
        )

    # کوتاه کردن خلاصه خیلی طولانی
    if len(summary) > 420:
        summary = (
            summary[:417].rstrip()
            + "..."
        )

    return summary


def build_source(source):
    source = clean_text(source)

    if not source:
        return "منبع نامشخص"

    return source


def format_news(item):
    title = normalize_title(
        item.get("title", "")
    )

    summary = build_summary(
        item
    )

    source = build_source(
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


def build_telegram_preview(item):
    """
    متن پیشنهادی برای انتشار آینده در تلگرام.
    فعلاً ارسال انجام نمی‌شود.
    """

    title = item.get(
        "title",
        "",
    )

    summary = item.get(
        "summary",
        "",
    )

    source = item.get(
        "source",
        "",
    )

    link = item.get(
        "link",
        "",
    )

    return (
        f"📰 {title}\n\n"
        f"{summary}\n\n"
        f"📌 منبع: {source}\n"
        f"🔗 {link}"
    )


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

        formatted["telegram_preview"] = (
            build_telegram_preview(
                formatted
            )
        )

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
    print("Sample output:")

    for item in ready_news[:5]:
        print()
        print(
            "TITLE:",
            item["title"],
        )
        print(
            "SUMMARY:",
            item["summary"],
        )
        print(
            "SOURCE:",
            item["source"],
        )
        print(
            "LINK:",
            item["link"],
        )
        print(
            "TELEGRAM PREVIEW:"
        )
        print(
            item[
                "telegram_preview"
            ]
        )


if __name__ == "__main__":
    main()
