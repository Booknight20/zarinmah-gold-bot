import json
import os
import re
from difflib import SequenceMatcher


INPUT_FILE = "news_ranked.json"
OUTPUT_FILE = "news_unique.json"


# اولویت منابع
SOURCE_PRIORITY = {
    "Reuters": 100,
    "Kitco": 95,
    "Trading Economics": 90,
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


def normalize_text(text):
    text = text or ""

    text = text.replace("ي", "ی")
    text = text.replace("ى", "ی")
    text = text.replace("ك", "ک")
    text = text.replace("ۀ", "ه")
    text = text.replace("ة", "ه")
    text = text.replace("\u200c", " ")
    text = text.replace("\u200f", " ")
    text = text.replace("\ufeff", " ")

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = re.sub(
        r"[«»“”\"'`،؛:,.!?؟()\[\]{}<>/\\|*_+=~\-–—]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip().lower()


def tokenize(text):
    normalized = normalize_text(text)

    common_words = {
        "امروز",
        "جدید",
        "آخرین",
        "گزارش",
        "خبر",
        "اعلام",
        "جزئیات",
        "مهم",
        "تازه",
        "شد",
        "شدند",
        "کرد",
        "کردند",
        "است",
        "هست",
        "به",
        "از",
        "در",
        "با",
        "برای",
        "این",
        "آن",
        "یک",
        "و",
        "که",
        "را",
        "بر",
    }

    return {
        word
        for word in normalized.split()
        if len(word) > 1
        and word not in common_words
    }


def get_source_priority(item):
    source = item.get("source", "")
    return SOURCE_PRIORITY.get(source, 50)


def get_score(item):
    try:
        return float(
            item.get(
                "market_score",
                0,
            )
        )
    except Exception:
        return 0


def similarity(title1, title2):
    normalized1 = normalize_text(title1)
    normalized2 = normalize_text(title2)

    if not normalized1 or not normalized2:
        return 0

    if normalized1 == normalized2:
        return 1.0

    text_similarity = SequenceMatcher(
        None,
        normalized1,
        normalized2,
    ).ratio()

    tokens1 = tokenize(title1)
    tokens2 = tokenize(title2)

    if not tokens1 or not tokens2:
        token_similarity = 0
    else:
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        token_similarity = (
            len(intersection) / len(union)
            if union
            else 0
        )

    # ترکیب شباهت متنی و کلمه‌ای
    return (
        text_similarity * 0.55
        + token_similarity * 0.45
    )


def are_same_story(item1, item2):
    title1 = item1.get("title", "")
    title2 = item2.get("title", "")

    score = similarity(
        title1,
        title2,
    )

    # تقریباً همان تیتر
    if score >= 0.88:
        return True

    # برای تیترهایی که تفاوت بیشتری دارند،
    # اگر چند کلمه کلیدی اصلی مشترک باشند
    # و شباهت مناسب باشد، یک خبر در نظر گرفته می‌شوند.
    if score >= 0.76:
        tokens1 = tokenize(title1)
        tokens2 = tokenize(title2)

        shared = tokens1 & tokens2

        important_shared_words = {
            word
            for word in shared
            if len(word) >= 4
        }

        if len(important_shared_words) >= 3:
            return True

    return False


def choose_best(item1, item2):
    score1 = get_score(item1)
    score2 = get_score(item2)

    # اول اهمیت بازار
    if score1 != score2:
        return item1 if score1 > score2 else item2

    # بعد اعتبار منبع
    priority1 = get_source_priority(item1)
    priority2 = get_source_priority(item2)

    if priority1 != priority2:
        return (
            item1
            if priority1 > priority2
            else item2
        )

    # در نهایت اگر امتیاز و منبع برابر بود،
    # خبر جدیدتر را نگه می‌داریم.
    date1 = item1.get(
        "published",
        "",
    )

    date2 = item2.get(
        "published",
        "",
    )

    return (
        item1
        if date1 >= date2
        else item2
    )


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

        return (
            data
            if isinstance(data, list)
            else []
        )

    except Exception as error:
        print(
            "Could not load ranked news:"
        )
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


def deduplicate_news(news):
    unique_news = []

    for item in news:
        duplicate_index = None

        for index, old_item in enumerate(
            unique_news
        ):
            if are_same_story(
                item,
                old_item,
            ):
                duplicate_index = index
                break

        if duplicate_index is None:
            unique_news.append(item)
        else:
            best_item = choose_best(
                item,
                unique_news[
                    duplicate_index
                ],
            )

            unique_news[
                duplicate_index
            ] = best_item

    return unique_news


def main():
    print("===================================")
    print("ZarinMah News Deduper")
    print("===================================")

    news = load_news()

    print(
        "Input news:",
        len(news),
    )

    unique_news = deduplicate_news(
        news
    )

    # مهم‌ترین خبرها اول
    unique_news.sort(
        key=lambda item: get_score(
            item
        ),
        reverse=True,
    )

    save_news(unique_news)

    print(
        "Unique news:",
        len(unique_news),
    )

    print(
        "Duplicates removed:",
        len(news) - len(unique_news),
    )

    print()
    print("Top unique news:")

    for item in unique_news[:10]:
        print(
            "-",
            item.get("source"),
            "|",
            item.get("market_score"),
            "|",
            item.get("title"),
        )


if __name__ == "__main__":
    main()
