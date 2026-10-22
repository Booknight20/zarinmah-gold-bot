
import json
import os
import re
import html
import tempfile
from difflib import SequenceMatcher


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

    invalid_count = sum(
        1 for item in data
        if not isinstance(item, dict)
    )

    if invalid_count:
        print("Invalid records skipped:", invalid_count)

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

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


# =========================================================
# پاک‌سازی متن
# =========================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)

    # تبدیل موجودیت‌های HTML پیش از پاک‌سازی تگ‌ها
    text = html.unescape(text)

    # حفظ شکست خطوط میان بخش‌های مختلف متن
    text = re.sub(
        r"(?i)<br\s*/?>",
        "\n",
        text,
    )

    text = re.sub(
        r"(?i)</(?:p|div|li|h[1-6]|blockquote|article|section)\s*>",
        "\n",
        text,
    )

    text = re.sub(
        r"(?i)<(?:p|div|li|h[1-6]|blockquote|article|section)\b[^>]*>",
        "",
        text,
    )

    # حذف تگ‌های باقی‌مانده
    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    # یکسان‌سازی نویسه‌های نامرئی
    text = text.replace("\u200f", "")
    text = text.replace("\u200e", "")
    text = text.replace("\ufeff", "")
    text = text.replace("\u00a0", " ")
    text = text.replace("\u202f", " ")

    # حفظ نیم‌فاصله فارسی
    text = text.replace("\u200c", "‌")

    # پاک‌سازی فاصله‌ها بدون حذف شکست خطوط
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

    text = text.replace("\u200c", " ")

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip().lower()


# =========================================================
# انتخاب متن‌های معتبر و جلوگیری از تکرار
# =========================================================

def unique_text_values(*values):
    """
    متن‌های غیرخالی و متمایز را نگه می‌دارد.
    متن‌های تکراری پس از نرمال‌سازی حذف می‌شوند.
    """

    result = []
    seen = set()

    for value in values:
        text = clean_text(value)

        if not text:
            continue

        normalized = normalize_for_comparison(text)

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        result.append(text)

    return result


def choose_best_text(*values):
    """
    از میان چند نسخه یک متن، طولانی‌ترین نسخه معتبر را انتخاب
    می‌کند؛ ترتیب فیلدها باعث انتخاب متن کوتاه‌تر نمی‌شود.
    """

    candidates = unique_text_values(*values)

    if not candidates:
        return ""

    return max(
        candidates,
        key=len,
    )


def choose_full_text(*values):
    """
    متن کامل را از تمام فیلدهای محتوایی بررسی می‌کند.

    1. متن‌های خالی و تکراری حذف می‌شوند.
    2. متن‌های کوتاه‌تر که داخل متن بلندتر هستند دوباره اضافه نمی‌شوند.
    3. متن‌های متمایز و مفید، در صورت عدم شباهت زیاد، حفظ می‌شوند.
    4. هیچ سقف طولی برای متن تعیین نمی‌شود.
    """

    candidates = unique_text_values(*values)

    if not candidates:
        return ""

    candidates.sort(
        key=len,
        reverse=True,
    )

    accepted = []
    accepted_normalized = []

    for candidate in candidates:
        normalized = normalize_for_comparison(candidate)

        if not normalized:
            continue

        is_redundant = False

        for old_normalized in accepted_normalized:
            # اگر یک متن داخل متن دیگر باشد، دوباره اضافه نشود.
            if (
                normalized in old_normalized
                or old_normalized in normalized
            ):
                is_redundant = True
                break

            # جلوگیری از تکرار متن‌های تقریباً یکسان
            similarity = SequenceMatcher(
                None,
                normalized,
                old_normalized,
            ).ratio()

            if similarity >= 0.90:
                is_redundant = True
                break

        if not is_redundant:
            accepted.append(candidate)
            accepted_normalized.append(normalized)

    return "\n\n".join(accepted)


# =========================================================
# آماده‌سازی عنوان
# =========================================================

def build_title(title):
    title = clean_text(title)

    if not title:
        return ""

    # فقط عبارت زمانی انتهایی مشخص حذف می‌شود.
    # طول عنوان محدود نمی‌شود.
    title = re.sub(
        r"\s*[-|،,]\s*"
        r"(?:امروز|دیروز|فردا)\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    return title


# =========================================================
# آماده‌سازی خلاصه
# =========================================================

def build_summary(summary):
    summary = clean_text(summary)

    if not summary:
        return ""

    # حذف عبارت معرفی منبع فقط از ابتدای متن
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
    مناسب فیلدهایی مانند عنوان، منبع و لینک است.
    """

    for value in values:
        text = clean_text(value)

        if text:
            return text

    return ""


def format_news(item):
    # تمام فیلدهای قبلی، از جمله اطلاعات رتبه‌بندی،
    # ابتدا حفظ می‌شوند.
    formatted = dict(item)

    # عنوان
    original_title = choose_text(
        item.get("title"),
        item.get("headline"),
    )

    title = build_title(original_title)

    # خلاصه: طولانی‌ترین نسخه از summary و description
    original_summary = choose_best_text(
        item.get("summary"),
        item.get("description"),
    )

    summary = build_summary(
        original_summary
    )

    # متن کامل:
    # تمام فیلدهای محتوایی بررسی می‌شوند؛
    # وجود full_text مانع بررسی content و text نمی‌شود.
    original_full_text = choose_full_text(
        item.get("full_text"),
        item.get("full_content"),
        item.get("content"),
        item.get("text"),
    )

    full_text = clean_text(
        original_full_text
    )

    # اگر خلاصه وجود ندارد، از متن کامل استفاده می‌شود.
    if not summary:
        summary = build_summary(
            full_text
        )

    # اگر متن کامل وجود ندارد، خلاصه حفظ می‌شود.
    if not full_text:
        full_text = summary

    # تکمیل اطلاعات اصلی بدون جعل داده
    formatted.update({
        "title": title,
        "summary": summary,
        "full_text": full_text,
        "source": clean_text(
            item.get("source", "")
        ),
        "link": str(
            item.get("link", "") or ""
        ).strip(),
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

    # اگر ورودی وجود نداشته باشد یا خراب باشد،
    # خروجی قبلی تغییر نمی‌کند.
    news = load_news()

    ready_news = []
    skipped = 0
    missing_summary = 0
    missing_full_text = 0

    for item in news:
        formatted = format_news(item)

        # عنوان و لینک برای انتشار الزامی هستند.
        if not formatted.get("title"):
            skipped += 1
            continue

        if not formatted.get("link"):
            skipped += 1
            continue

        if not formatted.get("summary"):
            missing_summary += 1

        if not formatted.get("full_text"):
            missing_full_text += 1

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
    print("Without summary:", missing_summary)
    print("Without full text:", missing_full_text)
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
