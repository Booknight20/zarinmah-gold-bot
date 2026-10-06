import json
import os
import re


NEWS_FILE = "news_items.json"
FILTERED_FILE = "news_filtered.json"


# بازارهای هدف
MARKET_KEYWORDS = {
    "gold": [
        "طلا",
        "اونس طلا",
        "اونس جهانی",
        "طلای جهانی",
        "طلای آبشده",
        "آبشده",
        "مثقال طلا",
        "گرم طلا",
        "طلای ۱۸ عیار",
        "طلای 24 عیار",
    ],
    "currency": [
        "دلار",
        "دلار آزاد",
        "دلار آمریکا",
        "نرخ دلار",
        "ارز",
        "نرخ ارز",
        "بازار ارز",
        "یورو",
        "درهم",
        "پوند",
        "ریال",
        "مرکز مبادله",
        "حراج ارز",
    ],
    "stock": [
        "بورس",
        "بازار سرمایه",
        "شاخص کل",
        "شاخص هم وزن",
        "فرابورس",
        "ارزش معاملات",
        "ورود پول حقیقی",
        "خروج پول حقیقی",
        "عرضه اولیه",
        "صف خرید",
        "صف فروش",
        "دامنه نوسان",
        "شاخص بورس",
    ],
}


# عوامل اقتصادی و پولی مؤثر بر بازارها
ECONOMIC_DRIVER_KEYWORDS = [
    "بانک مرکزی",
    "نرخ بهره",
    "سیاست پولی",
    "تورم",
    "نقدینگی",
    "پایه پولی",
    "فدرال رزرو",
    "fed",
    "cpi",
    "pce",
    "تورم آمریکا",
    "اشتغال آمریکا",
    "بازده اوراق",
    "اوراق خزانه آمریکا",
    "شاخص دلار",
    "dxy",
    "قیمت نفت",
    "نفت",
    "تحریم",
    "تحریم نفتی",
    "صادرات نفت",
    "ذخایر ارزی",
    "سیاست ارزی",
    "کسری بودجه",
    "بودجه",
    "رشد اقتصادی",
    "رکود",
]


# رویدادهایی که می‌توانند اثر جدی اقتصادی/بازاری داشته باشند
MAJOR_EVENT_KEYWORDS = [
    "ایران و آمریکا",
    "ایران آمریکا",
    "مذاکرات ایران و آمریکا",
    "مذاکرات هسته‌ای",
    "برجام",
    "تحریم‌های جدید",
    "تحریم جدید",
    "جنگ",
    "آتش‌بس",
    "تنش نظامی",
    "تنش منطقه‌ای",
    "درگیری منطقه‌ای",
    "تنگه هرمز",
]


def normalize_text(text):
    text = text or ""

    text = text.replace("ي", "ی")
    text = text.replace("ى", "ی")
    text = text.replace("ك", "ک")
    text = text.replace("ۀ", "ه")
    text = text.replace("ة", "ه")

    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def load_news():
    if not os.path.exists(NEWS_FILE):
        return []

    try:
        with open(
            NEWS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return data if isinstance(data, list) else []

    except Exception as error:
        print("Could not load news:", error)
        return []


def save_filtered_news(news):
    with open(
        FILTERED_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            news,
            file,
            ensure_ascii=False,
            indent=2,
        )


def find_matches(text, keywords):
    matches = []

    for keyword in keywords:
        keyword_normalized = normalize_text(keyword)

        if keyword_normalized in text:
            matches.append(keyword)

    return matches


def analyze_news(item):
    title = item.get("title", "")
    text = normalize_text(title)

    market_matches = {}
    total_market_matches = 0

    for market_name, keywords in MARKET_KEYWORDS.items():
        matches = find_matches(
            text,
            keywords,
        )

        if matches:
            market_matches[market_name] = matches
            total_market_matches += len(matches)

    driver_matches = find_matches(
        text,
        ECONOMIC_DRIVER_KEYWORDS,
    )

    major_event_matches = find_matches(
        text,
        MAJOR_EVENT_KEYWORDS,
    )

    # امتیاز
    score = 0

    # خبر مستقیم بازار امتیاز بالایی می‌گیرد
    score += total_market_matches * 3

    # عوامل اقتصادی امتیاز می‌دهند
    score += len(driver_matches) * 2

    # رویدادهای مهم ژئوپلیتیک
    score += len(major_event_matches) * 2

    # قوانین ورود به فیلتر
    include = False

    # 1) خبر مستقیم طلا/ارز/بورس
    if total_market_matches >= 1:
        include = True

    # 2) حداقل دو عامل اقتصادی مستقل
    elif len(driver_matches) >= 2:
        include = True

    # 3) رویداد مهم + عامل اقتصادی
    elif (
        len(major_event_matches) >= 1
        and len(driver_matches) >= 1
    ):
        include = True

    return {
        "include": include,
        "score": score,
        "market_matches": market_matches,
        "driver_matches": driver_matches,
        "major_event_matches": major_event_matches,
    }


def main():
    print("===================================")
    print("ZarinMah Market News Filter")
    print("===================================")

    news = load_news()

    filtered_news = []

    for item in news:
        analysis = analyze_news(item)

        if not analysis["include"]:
            continue

        new_item = dict(item)

        new_item["market_score"] = analysis["score"]
        new_item["market_matches"] = analysis["market_matches"]
        new_item["driver_matches"] = analysis["driver_matches"]
        new_item["major_event_matches"] = analysis[
            "major_event_matches"
        ]

        filtered_news.append(new_item)

    # خبرهای قوی‌تر اول
    filtered_news.sort(
        key=lambda item: item.get(
            "market_score",
            0,
        ),
        reverse=True,
    )

    save_filtered_news(filtered_news)

    print("Total news:", len(news))
    print("Market-related news:", len(filtered_news))

    print()
    print("Top filtered news:")

    for item in filtered_news[:10]:
        print(
            "-",
            item.get("market_score"),
            "|",
            item.get("title"),
        )


if __name__ == "__main__":
    main()
