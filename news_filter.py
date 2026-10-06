import json
import os


NEWS_FILE = "news_items.json"
FILTERED_FILE = "news_filtered.json"


STRONG_KEYWORDS = [
    # طلا
    "طلا",
    "طلای جهانی",
    "اونس طلا",
    "اونس جهانی",
    "طلای آبشده",
    "آبشده",
    "مثقال طلا",

    # سکه
    "سکه",
    "سکه امامی",
    "بهار آزادی",
    "نیم سکه",
    "ربع سکه",

    # ارز
    "دلار",
    "دلار آزاد",
    "دلار آمریکا",
    "یورو",
    "پوند",
    "درهم",
    "لیر",
    "ریال",

    # بانک مرکزی و سیاست پولی
    "بانک مرکزی",
    "نرخ بهره",
    "سیاست پولی",
    "نقدینگی",
    "پایه پولی",

    # عوامل مهم جهانی
    "فدرال رزرو",
    "FED",
    "تورم آمریکا",
    "شاخص قیمت مصرف کننده",
    "CPI",
    "PCE",
    "اشتغال آمریکا",
    "بازده اوراق",
    "اوراق خزانه آمریکا",

    # عوامل مهم داخلی
    "مرکز مبادله",
    "حراج سکه",
    "عرضه سکه",
    "ذخایر ارزی",
    "نرخ ارز",
    "بازار ارز",

        # بورس و بازار سرمایه
    "بورس",
    "بازار سرمایه",
    "شاخص کل",
    "شاخص هم وزن",
    "فرابورس",
    "ورود پول حقیقی",
    "خروج پول حقیقی",
    "ارزش معاملات",
    "عرضه اولیه",
]


SECONDARY_KEYWORDS = [
    "تورم",
    "تحریم",
    "صادرات نفت",
    "قیمت نفت",
    "نفت",
    "بورس",
]


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


def is_relevant(item):
    title = item.get("title", "").strip()

    if not title:
        return False

    title_lower = title.lower()

    strong_matches = [
        keyword.lower()
        for keyword in STRONG_KEYWORDS
        if keyword.lower() in title_lower
    ]

    if strong_matches:
        return True

    secondary_matches = [
        keyword.lower()
        for keyword in SECONDARY_KEYWORDS
        if keyword.lower() in title_lower
    ]

    return len(secondary_matches) >= 2


def main():
    print("===================================")
    print("ZarinMah News Filter")
    print("===================================")

    news = load_news()

    filtered_news = [
        item
        for item in news
        if is_relevant(item)
    ]

    save_filtered_news(filtered_news)

    print("Total news:", len(news))
    print("Relevant news:", len(filtered_news))


if __name__ == "__main__":
    main()
