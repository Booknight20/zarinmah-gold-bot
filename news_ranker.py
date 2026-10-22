import json
import os
import re


INPUT_FILE = "news_filtered.json"
OUTPUT_FILE = "news_ranked.json"


# =========================================================
# بازارهای هدف
# =========================================================

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
        "سکه بهار آزادی",
        "نیم سکه",
        "ربع سکه",
        "سکه گرمی",
        "سکه پارسیان",
        "طلای ۱۸ عیار",
        "طلای 18 عیار",
        "طلای ۲۴ عیار",
        "طلای 24 عیار",
        "صندوق طلا",
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
        "مرکز مبادله",
        "بازار متشکل ارزی",
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
        "صندوق درآمد ثابت",
        "بورس کالا",
    ],
}


# =========================================================
# عوامل مهم اقتصادی و سیاسی
# =========================================================

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
    "تصمیم بانک مرکزی",
    "توافق ایران",
    "حمله نظامی",
    "محدودیت صادرات نفت",
    "تغییر سیاست پولی",
    "تصمیم فدرال رزرو",
    "نرخ تورم",
    "تولید ناخالص داخلی",
    "gdp",
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
    "تحریم",
    "تراز تجاری",
    "نرخ بیکاری",
    "عرضه ارز",
    "تقاضای ارز",
    "سیاست مالی",
    "واردات",
    "صادرات",
    "تراز پرداخت‌ها",
    "تراز پرداخت ها",
]


# =========================================================
# نشانه‌های اطلاعات کاربردی بازار
# =========================================================

MARKET_SIGNAL_KEYWORDS = [
    "افزایش",
    "کاهش",
    "رشد",
    "افت",
    "صعود",
    "نزول",
    "سقوط",
    "جهش",
    "ریزش",
    "نوسان",
    "رکورد",
    "پیش‌بینی",
    "پیش بینی",
    "تحلیل",
    "چشم‌انداز",
    "چشم انداز",
    "قیمت",
    "نرخ",
    "معاملات",
    "عرضه",
    "تقاضا",
    "تصمیم",
    "تصویب",
    "ابلاغ",
    "تغییر",
    "ممنوعیت",
    "آزادسازی",
    "ورود پول",
    "خروج پول",
    "حمایت",
    "مقاومت",
    "هدف قیمتی",
    "بازدهی",
    "حباب",
    "حراج",
    "بازگشایی",
    "توقف معاملات",
    "گزارش مالی",
    "سود خالص",
    "زیان خالص",
    "مذاکرات",
    "توافق",
]


# =========================================================
# ابزارهای متن و فایل
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

    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


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

        if isinstance(data, list):
            return [
                item
                for item in data
                if isinstance(item, dict)
            ]

        print("Input JSON is not a list.")
        return []

    except Exception as error:
        print("Could not load news:", error)
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
    text = normalize_text(text)
    matches = []

    for keyword in keywords:
        keyword_normalized = normalize_text(keyword)

        if not keyword_normalized:
            continue

        pattern = (
            r"(?<!\w)"
            + re.escape(keyword_normalized)
            + r"(?:ی|ها|های)?"
            + r"(?!\w)"
        )

        if re.search(pattern, text):
            matches.append(keyword)

    return list(dict.fromkeys(matches))


def combine_matches(*match_lists):
    result = []

    for match_list in match_lists:
        for match in match_list:
            if match not in result:
                result.append(match)

    return result


def count_numeric_evidence(text):
    """
    فقط وجود رقم واقعی را بررسی می‌کند.
    کلماتی مثل «دلار» یا «تومان» به‌تنهایی
    مدرک عددی محسوب نمی‌شوند.
    """
    text = normalize_text(text)

    patterns = [
        r"\d+(?:[.,]\d+)?\s*%",
        r"\d+(?:[.,]\d+)?",
    ]

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


# =========================================================
# رتبه‌بندی خبر
# =========================================================

def rank_news(item):
    title = normalize_text(
        item.get("title", "")
    )

    summary = normalize_text(
        item.get("summary", "")
        or item.get("description", "")
    )

    text = normalize_text(
        title + " " + summary
    )

    # -----------------------------------------------------
    # تشخیص بازار در عنوان و خلاصه
    # -----------------------------------------------------

    title_market_matches = {}
    summary_market_matches = {}
    market_matches = {}

    for market_name, keywords in MARKET_KEYWORDS.items():
        title_matches = find_matches(
            title,
            keywords,
        )

        summary_matches = find_matches(
            summary,
            keywords,
        )

        combined = combine_matches(
            title_matches,
            summary_matches,
        )

        if title_matches:
            title_market_matches[market_name] = title_matches

        if summary_matches:
            summary_market_matches[market_name] = summary_matches

        if combined:
            market_matches[market_name] = combined

    gold_matches = market_matches.get("gold", [])
    currency_matches = market_matches.get("currency", [])
    stock_matches = market_matches.get("stock", [])

    high_title_matches = find_matches(
        title,
        HIGH_IMPACT_KEYWORDS,
    )

    high_summary_matches = find_matches(
        summary,
        HIGH_IMPACT_KEYWORDS,
    )

    medium_title_matches = find_matches(
        title,
        MEDIUM_IMPACT_KEYWORDS,
    )

    medium_summary_matches = find_matches(
        summary,
        MEDIUM_IMPACT_KEYWORDS,
    )

    signal_title_matches = find_matches(
        title,
        MARKET_SIGNAL_KEYWORDS,
    )

    signal_summary_matches = find_matches(
        summary,
        MARKET_SIGNAL_KEYWORDS,
    )

    high_impact_matches = combine_matches(
        high_title_matches,
        high_summary_matches,
    )

    medium_impact_matches = combine_matches(
        medium_title_matches,
        medium_summary_matches,
    )

    signal_matches = combine_matches(
        signal_title_matches,
        signal_summary_matches,
    )

    # -----------------------------------------------------
    # محاسبه امتیاز
    # -----------------------------------------------------

    score = 0

    # اشاره مستقیم در عنوان
    score += sum(
        len(matches) * 4
        for matches in title_market_matches.values()
    )

    # اشاره در خلاصه، با وزن کمتر
    score += sum(
        len(matches) * 2
        for matches in summary_market_matches.values()
    )

    # عوامل پراثر و متوسط
    score += len(high_impact_matches) * 4
    score += len(medium_impact_matches) * 2

    # وجود نشانه‌های اطلاعات کاربردی
    score += min(len(signal_matches), 4)

    # وجود رقم واقعی
    if count_numeric_evidence(text):
        score += 2

    # ارتباط هم‌زمان با چند بازار
    market_count = sum(
        bool(market_matches.get(market))
        for market in ("gold", "currency", "stock")
    )

    if market_count >= 2:
        score += 4

    # عنوان و خلاصه هر دو به بازار اشاره دارند
    if (
        title_market_matches
        and summary_market_matches
    ):
        score += 2

    # اگر فیلتر قبلی امتیاز ثبت کرده باشد،
    # فقط سهم محدودی در امتیاز نهایی دارد.
    # این کار مانع می‌شود امتیاز قبلی بر نتیجه مسلط شود.
    try:
        previous_filter_score = max(
            0,
            int(item.get("market_score", 0)),
        )
    except (TypeError, ValueError):
        previous_filter_score = 0

    filter_score_bonus = min(
        previous_filter_score,
        6,
    )

    score += filter_score_bonus

    # -----------------------------------------------------
    # تعیین اولویت
    # -----------------------------------------------------

    has_market = bool(market_matches)
    has_high_impact = bool(high_impact_matches)
    has_signal = bool(signal_matches)

    # امتیاز بالا به‌تنهایی کافی نیست:
    # خبر باید ارتباط مشخصی با بازار هدف داشته باشد.
    if (
        has_market
        and score >= 18
        and (
            has_signal
            or has_high_impact
            or market_count >= 2
        )
    ):
        priority = "high"

    elif has_market and score >= 9:
        priority = "medium"

    else:
        priority = "low"

    # -----------------------------------------------------
    # توضیح عوامل امتیازدهی برای بررسی بعدی
    # -----------------------------------------------------

    reasons = []

    if title_market_matches:
        reasons.append("ارتباط بازار در عنوان")

    if summary_market_matches:
        reasons.append("ارتباط بازار در خلاصه")

    if high_impact_matches:
        reasons.append("عامل پراثر اقتصادی یا سیاسی")

    if medium_impact_matches:
        reasons.append("عامل اقتصادی")

    if signal_matches:
        reasons.append("نشانه اطلاعات کاربردی بازار")

    if count_numeric_evidence(text):
        reasons.append("وجود رقم در متن")

    if market_count >= 2:
        reasons.append("ارتباط با چند بازار")

    return {
        "market_score": score,
        "priority": priority,
        "gold_matches": gold_matches,
        "currency_matches": currency_matches,
        "stock_matches": stock_matches,
        "market_matches": market_matches,
        "title_market_matches": title_market_matches,
        "summary_market_matches": summary_market_matches,
        "high_impact_matches": high_impact_matches,
        "medium_impact_matches": medium_impact_matches,
        "signal_matches": signal_matches,
        "ranking_reasons": reasons,
        "filter_score_bonus": filter_score_bonus,
    }


# =========================================================
# اجرای برنامه
# =========================================================

def main():
    print("===================================")
    print("ZarinMah News Ranker")
    print("===================================")

    news = load_news()
    ranked_news = []

    for item in news:
        # امتیاز مرحله فیلتر را قبل از محاسبه جدید حفظ می‌کنیم.
        new_item = dict(item)

        if "market_score" in new_item:
            new_item["filter_market_score"] = (
                new_item["market_score"]
            )

        analysis = rank_news(new_item)
        new_item.update(analysis)

        ranked_news.append(new_item)

    ranked_news.sort(
        key=lambda item: item.get("market_score", 0),
        reverse=True,
    )

    save_news(ranked_news)

    high_count = sum(
        item.get("priority") == "high"
        for item in ranked_news
    )

    medium_count = sum(
        item.get("priority") == "medium"
        for item in ranked_news
    )

    low_count = sum(
        item.get("priority") == "low"
        for item in ranked_news
    )

    print("Total ranked news:", len(ranked_news))
    print("High priority:", high_count)
    print("Medium priority:", medium_count)
    print("Low priority:", low_count)

    print()
    print("Top news:")

    for item in ranked_news[:10]:
        print(
            item.get("priority"),
            "|",
            item.get("market_score"),
            "|",
            item.get("source", ""),
            "|",
            item.get("title", ""),
        )

    print()
    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
