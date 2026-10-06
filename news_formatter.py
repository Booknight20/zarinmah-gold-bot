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


def remove_source_opening(text):
    """
    حذف عبارت‌های معرفی منبع از ابتدای خلاصه،
    بدون حذف محتوای اصلی خبر.
    """

    text = clean_text(text)

    patterns = [
        r"^طبق اعلام(?:\s+[^،:؛.!؟]+){0,12}\s*(?:،|:|؛)\s*",
        r"^بر اساس اعلام(?:\s+[^،:؛.!؟]+){0,12}\s*(?:،|:|؛)\s*",
        r"^براساس اعلام(?:\s+[^،:؛.!؟]+){0,12}\s*(?:،|:|؛)\s*",
        r"^به گزارش(?:\s+[^،:؛.!؟]+){0,12}\s*(?:،|:|؛)\s*",
        r"^بنابر اعلام(?:\s+[^،:؛.!؟]+){0,12}\s*(?:،|:|؛)\s*",
        r"^برپایه اعلام(?:\s+[^،:؛.!؟]+){0,12}\s*(?:،|:|؛)\s*",
        r"^بر مبنای اعلام(?:\s+[^،:؛.!؟]+){0,12}\s*(?:،|:|؛)\s*",
        r"^طبق گزارش(?:\s+[^،:؛.!؟]+){0,12}\s*(?:،|:|؛)\s*",
        r"^به نقل از(?:\s+[^،:؛.!؟]+){0,12}\s*(?:،|:|؛)\s*",
    ]

    previous = None

    while previous != text:
        previous = text

        for pattern in patterns:
            text = re.sub(
                pattern,
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()

    return text


def remove_redundant_phrases(text):
    """
    حذف چند عبارت خبری رایج که ارزش محتوایی ندارند.
    """

    patterns = [
        r"^این خبر می‌افزاید[،:؛]\s*",
        r"^این خبر می‌گوید[،:؛]\s*",
        r"^در همین حال[،:؛]\s*",
        r"^همچنین[،:؛]\s*",
    ]

    for pattern in patterns:
        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

    return text


def remove_date_and_time(title):
    title = clean_text(title)

    title = re.sub(
        r"\b(?:[۰-۹0-9]{1,2})\s+"
        r"(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|"
        r"مهر|آبان|آذر|دی|بهمن|اسفند)\s+"
        r"[۰-۹0-9]{4}\b",
        "",
        title,
    )

    title = re.sub(
        r"\b[۰-۹0-9]{1,2}[/-][۰-۹0-9]{1,2}[/-][۰-۹0-9]{2,4}\b",
        "",
        title,
    )

    title = re.sub(
        r"\b(?:امروز|دیروز|فردا|"
        r"دوشنبه|سه شنبه|سه‌شنبه|چهارشنبه|"
        r"پنجشنبه|جمعه|شنبه|یکشنبه)\b",
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
        if len(title) > 85:
            title = title[:82].rstrip() + "..."

        return title

    if len(title) > 90:
        title = title[:87].rstrip() + "..."

    return title


def split_sentences(text):
    text = clean_text(text)

    if not text:
        return []

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

    summary = remove_source_opening(
        summary
    )

    summary = remove_redundant_phrases(
        summary
    )

    sentences = split_sentences(
        summary
    )

    # اگر خلاصه یک جمله طولانی باشد،
    # از نقطه‌ویرگول برای تقسیم آن استفاده می‌کنیم.
    if len(sentences) == 1:
        semicolon_parts = [
            part.strip()
            for part in summary.split("؛")
            if part.strip()
        ]

        if len(semicolon_parts) >= 2:
            sentences = semicolon_parts

    selected = sentences[:3]

    if not selected:
        selected = [
            summary
        ]

    result = "\n".join(
        selected
    ).strip()

    # جلوگیری از طولانی شدن بیش از حد متن
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
