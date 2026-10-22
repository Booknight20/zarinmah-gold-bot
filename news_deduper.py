import json
import os
import re
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit


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


# =========================================================
# لینک خبر
# =========================================================

def canonical_url(url):
    """
    پارامترهای رهگیری را حذف می‌کند تا لینک‌های
    یکسان با پارامترهای تبلیغاتی متفاوت شناسایی شوند.
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

        query_parts = []

        for part in parts.query.split("&"):
            if not part:
                continue

            key = part.split("=", 1)[0].lower()

            if key.startswith("utm_") or key in ignored_params:
                continue

            query_parts.append(part)

        return urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            "&".join(query_parts),
            "",
        ))

    except Exception:
        return url.rstrip("/")


# =========================================================
# اطلاعات هر خبر
# =========================================================

def get_source_priority(item):
    source = normalize_text(item.get("source", ""))
    return SOURCE_PRIORITY.get(source, 50)


def get_score(item):
    try:
        return float(item.get("market_score", 0))
    except (TypeError, ValueError):
        return 0.0


def get_published(item):
    value = item.get("published", "")
    return str(value or "").strip()


def get_title(item):
    return normalize_text(item.get("title", ""))


def get_summary(item):
    return normalize_text(
        item.get("summary", "")
        or item.get("description", "")
    )


def extract_numbers(text):
    """
    اعداد موجود در متن را حفظ می‌کند تا مثلاً
    تغییر قیمت از ۷۰ به ۷۵ اشتباهاً نادیده گرفته نشود.
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
    فقط وقتی خبرها به‌اندازه کافی شبیه باشند
    و نشانه مهمی از تفاوت محتوایی نداشته باشند،
    یکی از آن‌ها حذف می‌شود.
    """

    title1 = get_title(item1)
    title2 = get_title(item2)

    if not title1 or not title2:
        return False

    url1 = canonical_url(item1.get("link", ""))
    url2 = canonical_url(item2.get("link", ""))

    # لینک کاملاً یکسان، قوی‌ترین نشانه تکراری بودن است.
    if url1 and url2 and url1 == url2:
        return True

    summary1 = get_summary(item1)
    summary2 = get_summary(item2)

    combined1 = (title1 + " " + summary1).strip()
    combined2 = (title2 + " " + summary2).strip()

    # تفاوت اعداد در عنوان می‌تواند نشان‌دهنده
    # قیمت یا رویداد متفاوت باشد.
    if has_conflicting_numbers(title1, title2):
        return False

    title_score = text_similarity(title1, title2)

    # عنوان یکسان یا تقریباً یکسان
    if title_score >= 0.94:
        # اگر هر دو خلاصه موجود و کاملاً متفاوت باشند،
        # برای جلوگیری از حذف اشتباه، هر دو حفظ می‌شوند.
        if (
            len(summary1) >= 80
            and len(summary2) >= 80
            and text_similarity(summary1, summary2) < 0.30
        ):
            return False

        if has_conflicting_numbers(summary1, summary2):
            return False

        return True

    # برای عنوان‌های متفاوت‌تر، شباهت خلاصه نیز لازم است.
    if title_score >= 0.78:
        if not summary1 or not summary2:
            return False

        if has_conflicting_numbers(summary1, summary2):
            return False

        summary_score = text_similarity(
            summary1,
            summary2,
        )

        combined_score = text_similarity(
            combined1,
            combined2,
        )

        tokens1 = tokenize(title1)
        tokens2 = tokenize(title2)

        shared_tokens = tokens1 & tokens2

        if (
            len(shared_tokens) >= 3
            and summary_score >= 0.68
            and combined_score >= 0.75
        ):
            return True

    return False


# =========================================================
# انتخاب نسخه بهتر از خبر تکراری
# =========================================================

def choose_best(item1, item2):
    score1 = get_score(item1)
    score2 = get_score(item2)

    if score1 != score2:
        return item1 if score1 > score2 else item2

    priority1 = get_source_priority(item1)
    priority2 = get_source_priority(item2)

    if priority1 != priority2:
        return item1 if priority1 > priority2 else item2

    # اگر منبع و امتیاز برابر باشند، خلاصه کامل‌تر
    # می‌تواند نسخه مفیدتری برای مراحل بعد باشد.
    summary_length1 = len(get_summary(item1))
    summary_length2 = len(get_summary(item2))

    if summary_length1 != summary_length2:
        return (
            item1
            if summary_length1 > summary_length2
            else item2
        )

    # در نهایت تاریخ انتشار را مقایسه می‌کنیم.
    date1 = get_published(item1)
    date2 = get_published(item2)

    return item1 if date1 >= date2 else item2


# =========================================================
# خواندن و ذخیره فایل‌ها
# =========================================================

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
            item
            for item in data
            if isinstance(item, dict)
        ]

    except Exception as error:
        print("Could not load ranked news:", error)
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
            unique_news.append(item)
        else:
            unique_news[duplicate_index] = choose_best(
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

    print("Unique news:", len(unique_news))
    print("Duplicates removed:", len(news) - len(unique_news))
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
