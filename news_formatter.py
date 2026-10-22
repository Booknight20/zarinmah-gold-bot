```python
import json
import os
import re
import html
import tempfile


INPUT_FILE = "news_unique.json"
OUTPUT_FILE = "news_ready.json"


# =========================================================
# بارگذاری امن اخبار
# =========================================================

def load_news():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"فایل ورودی پیدا نشد: {INPUT_FILE}"
        )

    try:
        with open(
            INPUT_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"ساختار JSON فایل ورودی خراب است: {error}"
        ) from error

    if not isinstance(data, list):
        raise ValueError(
            "ساختار news_unique.json باید یک فهرست باشد."
        )

    return [
        item for item in data
        if isinstance(item, dict)
    ]


# =========================================================
# ذخیره امن خروجی
# =========================================================

def save_news(news):
    output_dir = os.path.dirname(
        os.path.abspath(OUTPUT_FILE)
    )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_dir,
            prefix=".news_ready_",
            suffix=".tmp",
            delete=False,
        ) as file:
            temp_path = file.name

            json.dump(
                news,
                file,
                ensure_ascii=False,
                indent=2,
            )

            file.write("\n")

        os.replace(
            temp_path,
            OUTPUT_FILE,
        )

    except Exception:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

        raise


# =========================================================
# پاک‌سازی متن
# =========================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)

    # حذف تگ‌های HTML و حفظ فاصله بین بخش‌ها
    text = re.sub(
        r"(?i)<br\s*/?>",
        "\n",
        text,
    )

    text = re.sub(
        r"(?i)</(?:p|div|li|h[1-6])\s*>",
        "\n",
        text,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    # تبدیل موجودیت‌های HTML
    text = html.unescape(text)

    # یکسان‌سازی برخی نویسه‌های نامرئی
    text = text.replace("\u200f", "")
    text = text.replace("\u200e", "")
    text = text.replace("\ufeff", "")
    text = text.replace("\u00a0", " ")

    # حفظ نیم‌فاصله فارسی
    text = text.replace("\u200c", "‌")

    # پاک‌سازی فاصله‌ها بدون حذف شکست خطوط مفید
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r" *\n *",
        "\n",
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


# =========================================================
# آماده‌سازی عنوان
# =========================================================

def build_title(title):
    title = clean_text(title)

    if not title:
        return ""

    # حذف فقط عبارت‌های زمانی انتهایی و مشخص
    title = re.sub(
        r"\s*[-|،,]\s*"
        r"(?:امروز|دیروز|فردا)\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    # عنوان را به دلیل طولانی بودن نمی‌بریم.
    return title


# =========================================================
# آماده‌سازی خلاصه
# =========================================================

def build_summary(summary):
    summary = clean_text(summary)

    if not summary:
        return ""

    # حذف عبارت معرفی منبع فقط در ابتدای متن،
    # بدون حذف بدنه اصلی خبر.
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


# =========================================================
# انتخاب متن خبر
# =========================================================

def choose_text(*values):
    """
    اولین متن غیرخالی را برمی‌گرداند.
    متن‌ها کوتاه یا محدود نمی‌شوند.
    """

    for value in values:
        text = clean_text(value)

        if text:
            return text

    return ""


def format_news(item):
    # حفظ متن اصلی و اطلاعات رتبه‌بندی
    formatted = dict(item)

    original_title = choose_text(
        item.get("title"),
        item.get("headline"),
    )

    original_summary = choose_text(
        item.get("summary"),
        item.get("description"),
    )

    original_full_text = choose_text(
        item.get("full_text"),
        item.get("full_content"),
        item.get("content"),
        item.get("text"),
        original_summary,
    )

    title = build_title(
        original_title
    )

    summary = build_summary(
        original_summary
    )

    # اگر خلاصه وجود نداشته باشد، از متن کامل استفاده می‌کنیم.
    if not summary:
        summary = build_summary(
            original_full_text
        )

    full_text = clean_text(
        original_full_text
    )

    # اگر متن کامل موجود نباشد، خلاصه حفظ می‌شود.
    if not full_text:
        full_text = summary

    formatted.update({
        "title": title,
        "summary": summary,
        "full_text": full_text,
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

    # این فیلدها در صورت وجود حفظ می‌شوند؛
    # اگر وجود نداشته باشند، چیزی جعل نمی‌کنیم.
    return formatted


# =========================================================
# پیش‌نمایش پیام
# =========================================================

def build_telegram_preview(item):
    parts = []

    title = item.get("title", "")
    summary = item.get("summary", "")
    source = item.get("source", "")
    link = item.get("link", "")

    if title:
        parts.append(
            f"📰 {title}"
        )

    if summary:
        parts.append(
            summary
        )

    if source:
        parts.append(
            f"📌 منبع: {source}"
        )

    if link:
        parts.append(
            f"🔗 {link}"
        )

    return "\n\n".join(parts)


# =========================================================
# اجرای اصلی
# =========================================================

def main():
    print("===================================")
    print("ZarinMah News Formatter")
    print("===================================")

    # در صورت نبودن یا خرابی ورودی، برنامه متوقف می‌شود
    # و خروجی قبلی دست‌نخورده باقی می‌ماند.
    news = load_news()

    ready_news = []
    skipped = 0

    for item in news:
        formatted = format_news(item)

        # خبر باید عنوان و لینک قابل پیگیری داشته باشد.
        if not formatted.get("title"):
            skipped += 1
            continue

        if not formatted.get("link"):
            skipped += 1
            continue

        formatted["telegram_preview"] = (
            build_telegram_preview(formatted)
        )

        ready_news.append(
            formatted
        )

    save_news(
        ready_news
    )

    print("Input news:", len(news))
    print("Ready news:", len(ready_news))
    print("Skipped news:", skipped)
    print("Saved:", OUTPUT_FILE)

    print()
    print("Sample output:")

    for item in ready_news[:3]:
        print()
        print(
            item.get(
                "telegram_preview",
                "",
            )
        )


if __name__ == "__main__":
    main()
```
