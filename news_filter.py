import json
import os


NEWS_FILE = "news_items.json"
FILTERED_FILE = "news_filtered.json"


KEYWORDS = [
    "طلا",
    "سکه",
    "دلار",
    "ارز",
    "اونس",
    "بانک مرکزی",
    "نرخ بهره",
    "تورم",
    "اقتصاد",
    "بورس",
    "بازار",
    "نفت",
    "فدرال رزرو",
    "تحریم",
    "برجام",
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
    title = item.get("title", "")

    return any(
        keyword in title
        for keyword in KEYWORDS
    )


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
