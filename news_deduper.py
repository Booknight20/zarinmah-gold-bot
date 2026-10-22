import json
import os
import re
from difflib import SequenceMatcher
from urllib.parse import (
    urlsplit,
    urlunsplit,
    parse_qsl,
    urlencode,
)


INPUT_FILE = "news_ranked.json"
OUTPUT_FILE = "news_unique.json"


# =========================================================
# اولویت منابع
# =========================================================

SOURCE_PRIORITY = {
    "reuters": 100,
    "kitco": 95,
    "trading economics": 90,
    "دنیای اقتصاد": 88,
    "تسنیم": 85,
    "ایسنا": 82,
    "ایرنا": 82,
    "اقتصادنیوز": 80,
    "خبرآنلاین اقتصادی": 78,
    "مهر": 75,
    "ایلنا": 72,
    "تابناک": 65,
    "مشرق": 60,
}


# =========================================================
# نرمال‌سازی متن
# =========================================================

def normalize_text(text):
    if not isinstance(text, str):
        text = str(text or "")

    text = text.replace("ي", "ی")
    text = text.replace("ى", "ی")
    text = text.replace("ك", "ک")
    text = text.replace("ۀ", "ه")
    text = text.replace("ة", "ه")

    text = text.replace("\u200c", " ")
    text = text.replace("\u200f", " ")
    text = text.replace("\ufeff", " ")

    digit_map = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )
    text = text.translate(digit_map)

    text = re.sub(r"<[^>]+>", " ", text)

    text = re.sub(
        r"[«»“”\"'`،؛:,.!?؟()\[\]{}<>/\\|*_+=~\-–—]",
        " ",
        text,
    )

    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def tokenize(text):
    common_words = {
        "امروز", "جدید", "آخرین", "گزارش", "خبر",
        "اعلام", "جزئیات", "مهم", "تازه", "شد",
        "شدند", "کرد", "کردند", "است", "هست",
        "به", "از", "در", "با", "برای", "این",
        "آن", "یک", "و", "که", "را", "بر",
        "خواهد", "می‌شود", "میشود", "شدن",
    }

    return {
        word
        for word in normalize_text(text).split()
        if len(word) > 1 and word not in common_words
    }


def safe_float(value, default=0.0):
    try:
        if isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


# =========================================================
# لینک خبر
# =========================================================

def canonical_url(url):
    """
    پارامترهای رهگیری را حذف می‌کند و ترتیب پارامترهای
    باقی‌مانده را یکسان می‌کند.
    """

    if not isinstance(url, str) or not url.strip():
        return ""

    url = url.strip()

    try:
        parts = urlsplit(url)

        if not parts.scheme or not parts.netloc:
            return url.rstrip("/")

        ignored_params = {
            "fbclid",
            "gclid",
            "ref",
            "source",
            "campaign",
        }

        query_items = []

        for key, value in parse_qsl(
            parts.query,
            keep_blank_values=True,
        ):
            key_lower = key.lower()

            if (
                key_lower.startswith("utm_")
                or key_lower in ignored_params
            ):
                continue

            query_items.append((key, value))

        query_items.sort()

        netloc = parts.netloc.lower()
        scheme = parts.scheme.lower()
        path = parts.path.rstrip("/")

        return urlunsplit((
            scheme,
            netloc,
            path,
            urlencode(query_items, doseq=True),
            "",
        ))

    except Exception:
        return url.rstrip("/")


# =========================================================
# اطلاعات هر خبر
# =========================================================

def get_source_priority(item):
    source = normalize_text(item.get("source", ""))

    if source in SOURCE_PRIORITY:
        return SOURCE_PRIORITY[source]

    # تطبیق نام منبع در صورت وجود نام یا توضیحات اضافی
    for name, priority in SOURCE_PRIORITY.items():
        if name in source:
            return priority

    return 50


def get_score(item):
    return safe_float(item.get("market_score", 0), 0.0)


def get_published(item):
    return str(item.get("published", "") or "").strip()


def get_title(item):
    return normalize_text(item.get("title", ""))


def get_summary(item):
    return normalize_text(
        item.get("summary", "")
        or item.get("description", "")
    )


def get_full_text(item):
    return str(
        item.get("full_text", "")
        or item.get("content", "")
        or item.get("text", "")
        or ""
    ).strip()


def extract_numbers(text):
    """
    اعداد را برای جلوگیری از ادغام خبرهایی با قیمت‌ها
    یا مقادیر متفاوت استخراج می‌کند.
    """

    text = normalize_text(text)

    return re.findall(
        r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:\s*%)?",
        text,
    )


def has_conflicting_numbers(text1, text2):
    numbers1 = extract_numbers(text1)
    numbers2 = extract_numbers(text2)

    if not numbers1 or not numbers2:
        return False

    return numbers1 != numbers2


# =========================================================
# محاسبه شباهت
# =========================================================

def text_similarity(text1, text2):
    text1 = normalize_text(text1)
    text2 = normalize_text(text2)

    if not text1 or not text2:
        return 0.0

    if text1 == text2:
        return 1.0

    sequence_score = SequenceMatcher(
        None,
        text1,
        text2,
    ).ratio()

    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)

    if not tokens1 or not tokens2:
        token_score = 0.0
    else:
        union = tokens1 | tokens2
        token_score = (
            len(tokens1 & tokens2) / len(union)
            if union else 0.0
        )

    return sequence_score * 0.55 + token_score * 0.45


def are_same_story(item1, item2):
    """
    خبرها تنها زمانی تکراری محسوب می‌شوند که شواهد
    کافی از یکسان بودن موضوع و محتوا وجود داشته باشد.

    اختلاف مهم اعداد مانع ادغام خودکار می‌شود؛
    حتی اگر لینک‌ها یکسان باشند.
    """

    title1 = get_title(item1)
    title2 = get_title(item2)

    if not title1 or not title2:
        return False

    summary1 = get_summary(item1)
    summary2 = get_summary(item2)

    url1 = canonical_url(item1.get("link", ""))
    url2 = canonical_url(item2.get("link", ""))

    # اختلاف اعداد عنوان می‌تواند نشان‌دهنده رویداد
    # یا قیمت متفاوت باشد.
    if has_conflicting_numbers(title1, title2):
        return False

    # اگر هر دو خلاصه اطلاعات عددی متناقض دارند،
    # بدون شواهد قوی‌تر آن‌ها را یکی نمی‌کنیم.
    if (
        summary1
        and summary2
        and has_conflicting_numbers(summary1, summary2)
    ):
        return False

    # لینک یکسان، به‌تنهایی کافی نیست.
    # ابتدا سازگاری عنوان بررسی می‌شود.
    if url1 and url2 and url1 == url2:
        title_score = text_similarity(title1, title2)

        return title_score >= 0.65

    title_score = text_similarity(title1, title2)

    # عنوان تقریباً یکسان
    if title_score >= 0.94:
        if (
            len(summary1) >= 80
            and len(summary2) >= 80
            and text_similarity(summary1, summary2) < 0.30
        ):
            return False

        return True

    # برای عنوان‌هایی با شباهت متوسط، خلاصه نیز
    # باید شواهد کافی از یکسان بودن خبر داشته باشد.
    if title_score >= 0.78:
        if not summary1 or not summary2:
            return False

        summary_score = text_similarity(
            summary1,
            summary2,
        )

        combined1 = (title1 + " " + summary1).strip()
        combined2 = (title2 + " " + summary2).strip()

        combined_score = text_similarity(
            combined1,
            combined2,
        )

        shared_tokens = tokenize(title1) & tokenize(title2)

        if (
            len(shared_tokens) >= 3
            and summary_score >= 0.68
            and combined_score >= 0.75
        ):
            return True

    return False


# =========================================================
# انتخاب نسخه بهتر
# =========================================================

def choose_best(item1, item2):
    """
    نسخه اصلی را بر اساس امتیاز، اعتبار منبع،
    کامل بودن محتوا و تاریخ انتخاب می‌کند.
    """

    score1 = get_score(item1)
    score2 = get_score(item2)

    if score1 != score2:
        return dict(item1 if score1 > score2 else item2)

    priority1 = get_source_priority(item1)
    priority2 = get_source_priority(item2)

    if priority1 != priority2:
        return dict(
            item1 if priority1 > priority2 else item2
        )

    full_length1 = len(get_full_text(item1))
    full_length2 = len(get_full_text(item2))

    if full_length1 != full_length2:
        return dict(
            item1 if full_length1 > full_length2 else item2
        )

    summary_length1 = len(get_summary(item1))
    summary_length2 = len(get_summary(item2))

    if summary_length1 != summary_length2:
        return dict(
            item1 if summary_length1 > summary_length2 else item2
        )

    date1 = get_published(item1)
    date2 = get_published(item2)

    return dict(item1 if date1 >= date2 else item2)


# =========================================================
# ادغام اطلاعات مفید
# =========================================================

def merge_list_values(value1, value2):
    """
    دو فهرست را بدون حذف مقادیر یکتا ادغام می‌کند.
    """

    result = []

    for value in (value1, value2):
        if isinstance(value, list):
            for element in value:
                if element not in result:
                    result.append(element)

    return result


def merge_dict_values(value1, value2):
    """
    مقادیر دیکشنری را با حفظ کلیدهای هر دو رکورد ادغام می‌کند.
    """

    result = {}

    if isinstance(value1, dict):
        result.update(value1)

    if isinstance(value2, dict):
        for key, value in value2.items():
            if key not in result:
                result[key] = value
            elif isinstance(result[key], list) and isinstance(value, list):
                result[key] = merge_list_values(
                    result[key],
                    value,
                )

    return result


def merge_duplicate_records(item1, item2):
    """
    بهترین رکورد را به‌عنوان رکورد اصلی انتخاب می‌کند،
    سپس اطلاعات مفید رکورد دیگر را نیز حفظ می‌کند.
    """

    best = choose_best(item1, item2)
    other = item2 if best == item1 else item1

    merged = dict(best)

    # فیلدهای خالی رکورد اصلی با اطلاعات موجود
    # از رکورد دیگر تکمیل می‌شوند.
    for key, value in other.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            if value not in (None, "", [], {}):
                merged[key] = value

    # متن کامل را از رکورد دارای محتوای کامل‌تر انتخاب می‌کنیم.
    full_text1 = get_full_text(item1)
    full_text2 = get_full_text(item2)

    if len(full_text2) > len(full_text1):
        selected_full_text = full_text2
    else:
        selected_full_text = full_text1

    if selected_full_text:
        merged["full_text"] = selected_full_text

    # خلاصه کامل‌تر حفظ می‌شود.
    raw_summary1 = str(
        item1.get("summary", "")
        or item1.get("description", "")
        or ""
    ).strip()

    raw_summary2 = str(
        item2.get("summary", "")
        or item2.get("description", "")
        or ""
    ).strip()

    if len(raw_summary2) > len(raw_summary1):
        selected_summary = raw_summary2
    else:
        selected_summary = raw_summary1

    if selected_summary:
        merged["summary"] = selected_summary

    # امتیاز بالاتر و اولویت نهایی حفظ می‌شوند.
    merged["market_score"] = max(
        get_score(item1),
        get_score(item2),
    )

    priority_order = {
        "low": 1,
        "medium": 2,
        "high": 3,
    }

    priority1 = str(item1.get("priority", "low")).lower()
    priority2 = str(item2.get("priority", "low")).lower()

    merged["priority"] = max(
        (priority1, priority2),
        key=lambda value: priority_order.get(value, 0),
    )

    # داده‌های تشخیصی هر دو رکورد حفظ می‌شوند.
    list_fields = [
        "gold_matches",
        "currency_matches",
        "stock_matches",
        "high_impact_matches",
        "medium_impact_matches",
        "signal_matches",
        "ranking_reasons",
    ]

    for field in list_fields:
        merged[field] = merge_list_values(
            item1.get(field),
            item2.get(field),
        )

    dict_fields = [
        "market_matches",
        "title_market_matches",
        "summary_market_matches",
        "full_text_market_matches",
    ]

    for field in dict_fields:
        merged[field] = merge_dict_values(
            item1.get(field),
            item2.get(field),
        )

    # لینک رکورد اصلی حفظ می‌شود؛ لینک دیگر برای بررسی
    # منبع جایگزین در فهرستی جداگانه نگهداری می‌شود.
    links = merge_list_values(
        item1.get("alternate_links", []),
        item2.get("alternate_links", []),
    )

    for item in (item1, item2):
        link = item.get("link", "")

        if link and link != merged.get("link", ""):
            if link not in links:
                links.append(link)

    if links:
        merged["alternate_links"] = links

    sources = merge_list_values(
        item1.get("alternate_sources", []),
        item2.get("alternate_sources", []),
    )

    for item in (item1, item2):
        source = item.get("source", "")

        if source and source != merged.get("source", ""):
            if source not in sources:
                sources.append(source)

    if sources:
        merged["alternate_sources"] = sources

    # تعداد رکوردهای ادغام‌شده
    merged["duplicate_count"] = (
        max(1, safe_float(item1.get("duplicate_count", 1), 1))
        + max(1, safe_float(item2.get("duplicate_count", 1), 1))
    )

    return merged


# =========================================================
# خواندن و ذخیره فایل‌ها
# =========================================================

def load_news():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("Input JSON is not a list.")

        return [
            item
            for item in data
            if isinstance(item, dict)
        ]

    except (OSError, json.JSONDecodeError, ValueError) as error:
        print("Could not load ranked news:", error)
        raise


def save_news(news):
    temporary_file = OUTPUT_FILE + ".tmp"

    with open(
        temporary_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            news,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(temporary_file, OUTPUT_FILE)


# =========================================================
# حذف تکراری‌ها
# =========================================================

def deduplicate_news(news):
    unique_news = []

    for item in news:
        duplicate_index = None

        for index, old_item in enumerate(unique_news):
            if are_same_story(item, old_item):
                duplicate_index = index
                break

        if duplicate_index is None:
            new_item = dict(item)

            if "duplicate_count" not in new_item:
                new_item["duplicate_count"] = 1

            unique_news.append(new_item)

        else:
            unique_news[duplicate_index] = merge_duplicate_records(
                item,
                unique_news[duplicate_index],
            )

    return unique_news


# =========================================================
# اجرای برنامه
# =========================================================

def main():
    print("===================================")
    print("ZarinMah News Deduper")
    print("===================================")

    news = load_news()

    print("Input news:", len(news))

    unique_news = deduplicate_news(news)

    unique_news.sort(
        key=lambda item: get_score(item),
        reverse=True,
    )

    save_news(unique_news)

    duplicates_removed = len(news) - len(unique_news)

    print("Unique news:", len(unique_news))
    print("Duplicates removed:", duplicates_removed)
    print("Saved:", OUTPUT_FILE)

    print()
    print("Top unique news:")

    for item in unique_news[:10]:
        print(
            "-",
            item.get("source", ""),
            "|",
            item.get("market_score", 0),
            "|",
            item.get("title", ""),
        )


if __name__ == "__main__":
    main()
