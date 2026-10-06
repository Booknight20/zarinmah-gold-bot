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

    text = text.replace("\u200c", " ")
    text = text.replace("\u200f", " ")
    text = text.replace("\ufeff", " ")

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def remove_date_and_time(title):
    title = clean_text(title)

    # حذف تاریخ‌های شمسی با اعداد فارسی یا لاتین
    title = re.sub(
        r"\b(?:[۰-۹0-9]{1,2})\s+"
        r"(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|"
        r"مهر|آبان|آذر|دی|بهمن|اسفند)\s+"
        r"[۰-۹0-9]{4}\b",
        "",
        title,
    )

    # حذف تاریخ‌های عددی
    title = re.sub(
        r"\b[۰-۹0-9]{1,2}[/-][۰-۹0-9]{1,2}[/-][۰-۹0-9]{2,4}\b",
        "",
        title,
    )

    # حذف کلمات زمانی رایج
    title = re.sub(
        r"\b(?:امروز|دیروز|فردا|"
        r"دوشنبه|سه شنبه|چهارشنبه|پنجشنبه|جمعه|شنبه|یکشنبه)\b",
        "",
        title,
        flags=re.IGNORECASE,
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    ).strip()

    return title


def build_short_title(title):
    title = clean_text(title)

    title = remove_date_and_time(
        title
    )

    title = re.sub(
        r"^(?:نرخ|قیمت)\s+",
        "",
        title,
    )

    title = title.replace(
        " / ",
        "؛ ",
    )

    # برای تیترهای قیمتی رایج
    if (
        "دلار" in title
        and "طلا" in title
        and "یورو" in title
    ):
        return (
            "دلار، طلا و یورو؛ "
            "بازار امروز چه تغییری کرد؟"
        )

    if (
        "طلا" in title
        and "سکه" in title
    ):
        return (
            "طلا و سکه؛ "
            + title[:70]
        ).strip()

    if len(title) > 80:
        title = title[:77].rstrip() + "..."

    return title


def split_sentences(text):
    text = clean_text(text)

    if not text:
        return []

    # جدا کردن جمله با نقطه، علامت سؤال و نقطه‌ویرگول فارسی
    parts = re.split(
        r"(?<=[.!؟؛])\s+",
        text,
    )

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


def build_summary(summary):
    summary = clean_text(summary)

    if not summary:
        return (
            "جزئیات بیشتر در منبع اصلی "
            "خبر موجود است."
        )

    sentences = split_sentences(
        summary
    )

    # اگر متن یک جمله دارد، در محل نقطه‌ویرگول تقسیمش می‌کنیم
    if len(sentences) == 1 and "؛" in summary:
        parts = [
            part.strip()
            for part in summary.split("؛")
            if part.strip()
        ]

        if len(parts) >= 2:
            sentences = parts

    selected = sentences[:3]

    result = "\n".join(
        selected
    ).strip()

    if not result:
        result = summary

    if len(result) > 450:
        result = (
            result[:447].rstrip()
            + "..."
        )

    return result


def format_news(item):
    original_title = clean_text(
        item.get("title", "")
    )

    short_title = build_short_title(
        original_title
    )

    summary = build_summary(
        item.get("summary", "")
    )

    source = clean_text(
        item.get("source", "")
    )

    link = clean_text(
        item.get("link", "")
    )

    return {
        "title": short_title,
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
    return (
        f"📰 {item['title']}\n\n"
        f"{item['summary']}\n\n"
        f"📌 منبع: {item['source']}\n"
        f"🔗 {item['link']}"
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
            item["telegram_preview"]
        )


if __name__ == "__main__":
    main()
