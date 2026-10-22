import json
import os
import re


INPUT_FILE = "news_unique.json"
OUTPUT_FILE = "news_ready.json"


def load_news():
    if not os.path.exists(INPUT_FILE):
        print("Input file not found:", INPUT_FILE)
        return []

    try:
        with open(
            INPUT_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, list):
            print("Input JSON is not a list.")
            return []

        return [
            item for item in data
            if isinstance(item, dict)
        ]

    except Exception as error:
        print("Could not load news:", error)
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
    if text is None:
        return ""

    text = str(text)

    # حذف تگ‌های HTML
    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")

    text = text.replace("\u200c", "‌")
    text = text.replace("\u200f", "")
    text = text.replace("\ufeff", "")

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def normalize_for_comparison(text):
    text = clean_text(text)

    text = text.replace("ي", "ی")
    text = text.replace("ى", "ی")
    text = text.replace("ك", "ک")
    text = text.replace("ۀ", "ه")
    text = text.replace("ة", "ه")

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip().lower()


def build_title(title):
    """
    عنوان اصلی منبع حفظ می‌شود.
    فقط فاصله‌ها و عبارت‌های زمانی انتهایی
    در صورت اطمینان از بی‌اثر بودن حذف می‌شوند.
    """

    title = clean_text(title)

    if not title:
        return ""

    # حذف تاریخ یا ساعت فقط از انتهای عنوان؛
    # تاریخ‌های داخل عنوان دست‌نخورده می‌مانند.
    title = re.sub(
        r"\s*[-|،,]\s*"
        r"(?:امروز|دیروز|فردا)\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    if len(title) > 250:
        # عنوان طولانی را به‌جای بریدن،
        # کامل نگه می‌داریم تا معنای خبر از بین نرود.
        return title

    return title


def build_summary(summary):
    """
    خلاصه منبع را بدون محدودیت تعداد جمله یا نویسه حفظ می‌کند.
    فقط عبارت‌های تکراری ابتدای متن حذف می‌شوند،
    آن هم وقتی حذفشان به محتوای خبری لطمه نزند.
    """

    summary = clean_text(summary)

    if not summary:
        return ""

    # فقط عبارت‌های روشن و عمومی که به‌تنهایی
    # ارزش خبری ندارند، از ابتدای متن حذف می‌شوند.
    opening_patterns = [
        r"^به گزارش [^،:؛\n]{1,100}[،:؛]\s*",
        r"^طبق اعلام [^،:؛\n]{1,100}[،:؛]\s*",
        r"^بر اساس اعلام [^،:؛\n]{1,100}[،:؛]\s*",
        r"^براساس اعلام [^،:؛\n]{1,100}[،:؛]\s*",
        r"^بنابر اعلام [^،:؛\n]{1,100}[،:؛]\s*",
    ]

    for pattern in opening_patterns:
        summary = re.sub(
            pattern,
            "",
            summary,
            count=1,
            flags=re.IGNORECASE,
        )

    return summary.strip()


def format_news(item):
    original_title = clean_text(
        item.get("title", "")
    )

    original_summary = (
        item.get("summary", "")
        or item.get("description", "")
    )

    title = build_title(
        original_title
    )

    summary = build_summary(
        original_summary
    )

    # حفظ اطلاعات اصلی و شواهد رتبه‌بندی
    # تا در مراحل بعد از دست نروند.
    formatted = dict(item)

    formatted.update({
        "title": title,
        "summary": summary,
        "source": clean_text(
            item.get("source", "")
        ),
        "link": clean_text(
            item.get("link", "")
        ),
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
    })

    return formatted


def build_telegram_preview(item):
    parts = []

    title = item.get("title", "")
    summary = item.get("summary", "")
    source = item.get("source", "")
    link = item.get("link", "")

    if title:
        parts.append(f"📰 {title}")

    if summary:
        parts.append(summary)

    if source:
        parts.append(f"📌 منبع: {source}")

    if link:
        parts.append(f"🔗 {link}")

    return "\n\n".join(parts)


def main():
    print("===================================")
    print("ZarinMah News Formatter")
    print("===================================")

    news = load_news()
    ready_news = []

    for item in news:
        formatted = format_news(item)

        # خبر بدون عنوان یا لینک قابل پیگیری
        # برای انتشار آماده نمی‌شود.
        if not formatted["title"]:
            continue

        if not formatted["link"]:
            continue

        formatted["telegram_preview"] = (
            build_telegram_preview(formatted)
        )

        ready_news.append(formatted)

    save_news(ready_news)

    print("Input news:", len(news))
    print("Ready news:", len(ready_news))
    print("Skipped news:", len(news) - len(ready_news))
    print("Saved:", OUTPUT_FILE)

    print()
    print("Sample output:")

    for item in ready_news[:3]:
        print()
        print(item["telegram_preview"])


if __name__ == "__main__":
    main()
