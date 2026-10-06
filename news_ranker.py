import json
import os
import re


INPUT_FILE = "news_filtered.json"
OUTPUT_FILE = "news_ranked.json"


MARKET_KEYWORDS = {
    "gold": [
        "طلا",
        "اونس طلا",
        "اونس جهانی",
        "طلای جهانی",
        "آبشده",
        "طلای آبشده",
        "مثقال طلا",
        "سکه",
        "سکه امامی",
        "نیم سکه",
        "ربع سکه",
    ],
    "currency": [
        "دلار",
        "نرخ دلار",
        "بازار ارز",
        "نرخ ارز",
        "ارز",
        "یورو",
        "درهم",
        "پوند",
        "ریال",
        "مرکز مبادله",
    ],
    "stock": [
        "بورس",
        "بازار سرمایه",
        "شاخص کل",
        "شاخص هم وزن",
        "فرابورس",
        "ارزش معاملات",
        "عرضه اولیه",
        "ورود پول حقیقی",
        "خروج پول حقیقی",
        "صف خرید",
        "صف فروش",
    ],
}


HIGH_IMPACT_KEYWORDS = [
    "نرخ بهره",
    "فدرال رزرو",
    "بانک مرکزی",
    "تحریم جدید",
    "تحریم‌های جدید",
    "مذاکرات ایران و آمریکا",
    "مذاکرات هسته‌ای",
    "جنگ",
    "آتش‌بس",
    "تنش نظامی",
    "تنگه هرمز",
    "تورم آمریکا",
    "تورم",
    "شاخص دلار",
    "dxy",
    "قیمت نفت",
    "صادرات نفت",
    "سیاست ارزی",
    "ذخایر ارزی",
]


MEDIUM_IMPACT_KEYWORDS = [
    "نقدینگی",
    "پایه پولی",
    "کسری بودجه",
    "بودجه",
    "رشد اقتصادی",
    "رکود",
    "اشتغال آمریکا",
    "بازده اوراق",
    "اوراق خزانه آمریکا",
    "قیمت نفت",
    "تحریم",
]


IMPORTANT_NUMBERS = [
    "%",
    "درصد",
    "میلیون",
    "میلیارد",
    "تریلیون",
    "دلار",
    "ریال",
    "تومان",
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
    if not os.path.exists(INPUT_FILE):
        return []

    try:
        with open(
            INPUT_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return data if isinstance(data, list) else []

    except Exception as error:
        print("Could not load filtered news:")
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


def find_matches(text, keywords):
    matches = []

    for keyword in keywords:
        keyword_normalized = normalize_text(keyword)

        pattern = (
            r"(?<![\w])"
            + re.escape(keyword_normalized)
            + r"(?:ی|ها|های)?"
            + r"(?![\w])"
        )

        if re.search(pattern, text):
            matches.append(keyword)

    return matches


def rank_news(item):
    title = normalize_text(
        item.get("title", "")
    )

    summary = normalize_text(
        item.get("summary", "")
    )

    text = f"{title} {summary}".strip()

    gold_matches = find_matches(
        text,
        MARKET_KEYWORDS["gold"],
    )

    currency_matches = find_matches(
        text,
        MARKET_KEYWORDS["currency"],
    )

    stock_matches = find_matches(
        text,
        MARKET_KEYWORDS["stock"],
    )

    high_impact_matches = find_matches(
        text,
        HIGH_IMPACT_KEYWORDS,
    )

    medium_impact_matches = find_matches(
        text,
        MEDIUM_IMPACT_KEYWORDS,
    )

    number_matches = find_matches(
        text,
        IMPORTANT_NUMBERS,
    )

    score = 0

    # ارتباط مستقیم با بازار
    score += len(gold_matches) * 5
    score += len(currency_matches) * 5
    score += len(stock_matches) * 4

    # عوامل مهم اقتصادی و سیاسی
    score += len(high_impact_matches) * 5
    score += len(medium_impact_matches) * 2

    # وجود اعداد و تغییرات قیمتی معمولاً ارزش خبری بیشتری دارد
    if number_matches:
        score += 2

    # اگر خبر هم بازار هدف داشته باشد و هم عامل اثرگذار،
    # ارزش آن بیشتر می‌شود.
    market_count = sum(
        [
            bool(gold_matches),
            bool(currency_matches),
            bool(stock_matches),
        ]
    )

    if market_count >= 2:
        score += 5

    if (
        market_count >= 1
        and high_impact_matches
    ):
        score += 5

    # تعیین سطح اهمیت
    if score >= 18:
        priority = "high"
    elif score >= 10:
        priority = "medium"
    else:
        priority = "low"

    return {
        "market_score": score,
        "priority": priority,
        "gold_matches": gold_matches,
        "currency_matches": currency_matches,
        "stock_matches": stock_matches,
        "high_impact_matches": high_impact_matches,
        "medium_impact_matches": medium_impact_matches,
    }


def main():
    print("===================================")
    print("ZarinMah News Ranker")
    print("===================================")

    news = load_news()

    ranked_news = []

    for item in news:
        analysis = rank_news(item)

        new_item = dict(item)

        new_item.update(analysis)

        ranked_news.append(new_item)

    ranked_news.sort(
        key=lambda item: item.get(
            "market_score",
            0,
        ),
        reverse=True,
    )

    save_news(ranked_news)

    print(
        "Total ranked news:",
        len(ranked_news),
    )

    print()
    print("Top news:")

    for item in ranked_news[:10]:
        print(
            item.get("priority"),
            "|",
            item.get("market_score"),
            "|",
            item.get("title"),
        )


if __name__ == "__main__":
    main()
