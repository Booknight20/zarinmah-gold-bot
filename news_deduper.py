
import json
import os
import re
import tempfile
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

DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_text(text):
    if not isinstance(text, str):
        text = str(text or "")

    text = text.replace("ي", "ی")
    text = text.replace("ى", "ی")
    text = text.replace("ك", "ک")
    text = text.replace("ۀ", "ه")
    text = text.replace("ة", "ه")

    text = text.translate(DIGIT_MAP)

    text = text.replace("\u200c", " ")
    text = text.replace("\u200f", " ")
    text = text.replace("\u200e", " ")
    text = text.replace("\ufeff", " ")
    text = text.replace("\xa0", " ")

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


def safe_count(value, default=1):
    try:
        if isinstance(value, bool):
            return default

        result = int(float(value))

        return max(1, result)

    except (TypeError, ValueError, OverflowError):
        return default


def unique_text_fields(*values):
    result = []
    seen = set()

    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue

        normalized = normalize_text(value)

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        result.append(value.strip())

    return result


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

    for name, priority in SOURCE_PRIORITY.items():
        if normalize_text(name) in source:
            return priority

    return 50


def get_score(item):
    return safe_float(item.get("market_score", 0), 0.0)


def get_published(item):
    return str(item.get("published", "") or "").strip()


def get_title(item):
    return normalize_text(
        item.get("title", "") or item.get("headline", "")
    )


def get_summary(item):
    return normalize_text(
        item.get("summary", "")
        or item.get("description", "")
    )


def get_full_text(item):
    """
    تمام فیلدهای محتوایی را بررسی می‌کند.
    وجود full_text مانع بررسی content یا text نمی‌شود.
    """

    fields = unique_text_fields(
        item.get("full_text", ""),
        item.get("full_content", ""),
        item.get("content", ""),
        item.get("text", ""),
    )

    return "\n\n".join(fields)


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
        token_score = len(tokens1 & tokens2) / len(union)

    return sequence_score * 0.55 + token_score * 0.45


def are_same_story(item1, item2):
    """
    ادغام فقط با وجود شواهد کافی انجام می‌شود.
    اختلاف اعداد مهم، مانع ادغام خودکار است.
    """

    title1 = get_title(item1)
    title2 = get_title(item2)

    if not title1 or not title2:
        return False

    summary1 = get_summary(item1)
    summary2 = get_summary(item2)

    url1 = canonical_url(item1.get("link", ""))
    url2 = canonical_url(item2.get("link", ""))

    # قیمت یا عدد متفاوت در عنوان: ادغام ممنوع
    if has_conflicting_numbers(title1, title2):
        return False

    # اطلاعات عددی متناقض در خلاصه‌ها نیز با احتیاط
    # بررسی می‌شوند.
    if (
        summary1
        and summary2
        and has_conflicting_numbers(summary1, summary2)
    ):
        return False

    title_score = text_similarity(title1, title2)

    # لینک یکسان به‌تنهایی کافی نیست.
    if url1 and url2 and url1 == url2:
        return title_score >= 0.65

    # عنوان تقریباً یکسان
    if title_score >= 0.94:
        if (
            len(summary1) >= 80
            and len(summary2) >= 80
            and text_similarity(summary1, summary2) < 0.30
        ):
            return False

        return True

    # شباهت متوسط: خلاصه‌ها هم باید نزدیک باشند.
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

        return (
            len(shared_tokens) >= 3
            and summary_score >= 0.68
            and combined_score >= 0.75
        )

    return False


# =========================================================
# انتخاب نسخه بهتر
# =========================================================

def choose_best(item1, item2):
    """
    امتیاز بازار، اعتبار منبع و کامل بودن محتوا
    در انتخاب رکورد اصلی در نظر گرفته می‌شوند.
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
# ادغام داده‌ها
# =========================================================

def merge_list_values(value1, value2):
    result = []

    for value in (value1, value2):
        if isinstance(value, list):
            for element in value:
                if element not in result:
                    result.append(element)

    return result


def merge_dict_values(value1, value2):
    result = {}

    for value in (value1, value2):
        if not isinstance(value, dict):
            continue

        for key, item_value in value.items():
            if key not in result:
                result[key] = item_value
            elif (
                isinstance(result[key], list)
                and isinstance(item_value, list)
            ):
                result[key] = merge_list_values(
                    result[key],
                    item_value,
                )
            elif (
                isinstance(result[key], dict)
                and isinstance(item_value, dict)
            ):
                result[key] = merge_dict_values(
                    result[key],
                    item_value,
                )

    return result


def merge_duplicate_records(item1, item2):
    """
    بهترین رکورد را نگه می‌دارد و اطلاعات مفید رکورد
    دیگر را نیز اضافه می‌کند.
    """

    best = choose_best(item1, item2)
    other = item2 if best is item1 else item1

    merged = dict(best)

    # تکمیل فیلدهای خالی
    for key, value in other.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            if value not in (None, "", [], {}):
                merged[key] = value

    # نگهداری متن‌های موجود بدون حذف محتوای رکورد دیگر
    full_text_fields = unique_text_fields(
        item1.get("full_text", ""),
        item1.get("full_content", ""),
        item1.get("content", ""),
        item1.get("text", ""),
        item2.get("full_text", ""),
        item2.get("full_content", ""),
        item2.get("content", ""),
        item2.get("text", ""),
    )

    if full_text_fields:
        merged["full_text"] = "\n\n".join(full_text_fields)

    # خلاصه‌ها: خلاصه بلندتر اصلی می‌شود و خلاصه دیگر
    # در صورت متفاوت بودن در فهرست خلاصه‌های جایگزین می‌ماند.
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

    summaries = unique_text_fields(raw_summary1, raw_summary2)

    if summaries:
        selected_summary = max(summaries, key=len)
        merged["summary"] = selected_summary

        alternate_summaries = [
            summary for summary in summaries
            if summary != selected_summary
        ]

        if alternate_summaries:
            merged["alternate_summaries"] = merge_list_values(
                merged.get("alternate_summaries", []),
                alternate_summaries,
            )

    # حفظ بالاترین امتیاز رتبه‌بندی
    merged["market_score"] = max(
        get_score(item1),
        get_score(item2),
    )

    # حفظ امتیاز مرحله فیلتر بدون جایگزین کردن آن با امتیاز رتبه‌بندی
    filter_score1 = safe_float(
        item1.get("filter_market_score", 0), 0
    )
    filter_score2 = safe_float(
        item2.get("filter_market_score", 0), 0
    )

    merged["filter_market_score"] = max(
        filter_score1,
        filter_score2,
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

    # ادغام شواهد تشخیصی
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

    # لینک جایگزین
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

    # منابع جایگزین
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

    # شمارنده: هر رکورد می‌تواند قبلاً چند رکورد را نمایندگی کند.
    merged["duplicate_count"] = (
        safe_count(item1.get("duplicate_count", 1))
        + safe_count(item2.get("duplicate_count", 1))
    )

    return merged


# =========================================================
# خواندن و ذخیره فایل‌ها
# =========================================================

def load_news():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}. "
            "Output was not modified."
        )

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in {INPUT_FILE}: {error}"
        ) from error

    if not isinstance(data, list):
        raise ValueError(
            f"{INPUT_FILE} must contain a JSON list."
        )

    invalid_count = sum(
        1 for item in data if not isinstance(item, dict)
    )

    if invalid_count:
        print("Invalid records skipped:", invalid_count)

    return [
        item for item in data
        if isinstance(item, dict)
    ]


def save_news(news):
    directory = os.path.dirname(os.path.abspath(OUTPUT_FILE))
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix=".news_unique_",
            suffix=".tmp",
            delete=False,
        ) as file:
            json.dump(
                news,
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.write("\n")
            temp_path = file.name

        os.replace(temp_path, OUTPUT_FILE)

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


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
                unique_news[duplicate_index],
                item,
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
```
