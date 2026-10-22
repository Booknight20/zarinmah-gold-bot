
import json
import os
import re


NEWS_FILE = "news_items.json"
FILTERED_FILE = "news_filtered.json"


# =========================================================
# بازارهای هدف زرین ماه
# =========================================================

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
        "طلای 18 عیار",
        "طلای ۲۴ عیار",
        "طلای 24 عیار",
        "طلای ۲۱ عیار",
        "طلای 21 عیار",
        "سکه امامی",
        "سکه بهار آزادی",
        "نیم سکه",
        "ربع سکه",
        "سکه گرمی",
        "سکه پارسیان",
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
        "مرکز مبادله",
        "حراج ارز",
        "بازار متشکل ارزی",
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
        "صندوق طلا",
        "صندوق های طلا",
        "صندوق‌های طلا",
        "صندوق درآمد ثابت",
        "بورس کالا",
    ],
}


# =========================================================
# عوامل اقتصادی و پولی مؤثر بر بازارها
# =========================================================

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
    "تراز تجاری",
    "تولید ناخالص داخلی",
    "gdp",
    "نرخ بیکاری",
    "سیاست ارزی",
    "عرضه ارز",
    "تقاضای ارز",
    "کسری تجاری",
    "حجم نقدینگی",
    "پایه پولی",
    "سیاست مالی",
]


# =========================================================
# رویدادهای سیاسی و منطقه‌ای با اثر احتمالی اقتصادی
# =========================================================

MAJOR_EVENT_KEYWORDS = [
    "ایران و آمریکا",
    "ایران آمریکا",
    "مذاکرات ایران و آمریکا",
    "مذاکرات هسته‌ای",
    "مذاکرات هسته ای",
    "برجام",
    "تحریم‌های جدید",
    "تحریم های جدید",
    "تحریم جدید",
    "جنگ",
    "آتش‌بس",
    "آتش بس",
    "تنش نظامی",
    "تنش منطقه‌ای",
    "تنش منطقه ای",
    "درگیری منطقه‌ای",
    "درگیری منطقه ای",
    "تنگه هرمز",
    "مذاکرات ایران",
    "توافق ایران",
    "حمله نظامی",
    "حمله موشکی",
    "تحولات خاورمیانه",
    "شورای امنیت",
    "قطعنامه",
    "محدودیت صادرات نفت",
]


# =========================================================
# نشانه‌های تغییر، رویداد یا اطلاعات قابل استفاده
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
    "معامله",
    "معاملات",
    "عرضه",
    "تقاضا",
    "تصمیم",
    "تصویب",
    "ابلاغ",
    "تغییر",
    "ممنوعیت",
    "آزادسازی",
    "آزاد سازی",
    "ورود پول",
    "خروج پول",
    "حمایت",
    "مقاومت",
    "هدف قیمتی",
    "سود",
    "زیان",
    "بازدهی",
    "حباب",
    "حراج",
    "عرضه اولیه",
    "توقف معاملات",
    "بازگشایی",
    "گزارش مالی",
    "سود خالص",
    "زیان خالص",
    "تولید",
    "صادرات",
    "واردات",
    "توافق",
    "مذاکرات",
    "تصمیم گیری",
    "تصمیم‌گیری",
]


# =========================================================
# ابزارهای عمومی
# =========================================================

def normalize_text(text):
    if not isinstance(text, str):
        text = str(text or "")

    text = text.replace("ي", "ی")
    text = text.replace("ى", "ی")
    text = text.replace("ك", "ک")
    text = text.replace("ۀ", "ه")
    text = text.replace("ة", "ه")

    # یکسان‌سازی ارقام فارسی و عربی
    digit_map = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )
    text = text.translate(digit_map)

    # یکسان‌سازی فاصله‌ها
    text = text.replace("\u200c", " ")
    text = text.replace("\u200f", " ")
    text = text.replace("\ufeff", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def load_news():
    if not os.path.exists(NEWS_FILE):
        print("Input file not found:", NEWS_FILE)
        return []

    try:
        with open(
            NEWS_FILE,
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


def unique_matches(*match_lists):
    result = []

    for matches in match_lists:
        for match in matches:
            if match not in result:
                result.append(match)

    return result


# =========================================================
# تحلیل ارتباط و ارزش اولیه خبر
# =========================================================

def analyze_news(item):
    title = normalize_text(item.get("title", ""))
    summary = normalize_text(
        item.get("summary", "")
        or item.get("description", "")
    )

    # عنوان و خلاصه جداگانه بررسی می‌شوند.
    title_text = title
    summary_text = summary

    # ترکیب برای تشخیص کلی موضوع خبر
    full_text = normalize_text(
        title + " " + summary
    )

    market_matches = {}
    title_market_matches = {}
    summary_market_matches = {}

    total_title_market_matches = 0
    total_summary_market_matches = 0

    for market_name, keywords in MARKET_KEYWORDS.items():
        title_matches = find_matches(
            title_text,
            keywords,
        )

        summary_matches = find_matches(
            summary_text,
            keywords,
        )

        combined_matches = unique_matches(
            title_matches,
            summary_matches,
        )

        if combined_matches:
            market_matches[market_name] = combined_matches

        if title_matches:
            title_market_matches[market_name] = title_matches
            total_title_market_matches += len(title_matches)

        if summary_matches:
            summary_market_matches[market_name] = summary_matches
            total_summary_market_matches += len(summary_matches)

    driver_matches = find_matches(
        full_text,
        ECONOMIC_DRIVER_KEYWORDS,
    )

    major_event_matches = find_matches(
        full_text,
        MAJOR_EVENT_KEYWORDS,
    )

    title_signal_matches = find_matches(
        title_text,
        MARKET_SIGNAL_KEYWORDS,
    )

    summary_signal_matches = find_matches(
        summary_text,
        MARKET_SIGNAL_KEYWORDS,
    )

    signal_matches = unique_matches(
        title_signal_matches,
        summary_signal_matches,
    )

    # -----------------------------------------------------
    # امتیازدهی
    # -----------------------------------------------------

    score = 0

    # اشاره مستقیم در عنوان ارزش بیشتری دارد.
    score += total_title_market_matches * 4

    # اشاره به بازار در خلاصه نیز ارزش دارد.
    score += total_summary_market_matches * 2

    # عوامل اقتصادی و رویدادها
    score += len(driver_matches) * 2
    score += len(major_event_matches) * 2

    # نشانه‌های تغییر یا اطلاعات کاربردی
    score += min(len(signal_matches), 5)

    # وجود چند بازار هدف می‌تواند اهمیت بین‌بازاری داشته باشد.
    if len(market_matches) >= 2:
        score += 3

    # اگر عنوان و خلاصه هر دو به بازار مرتبط باشند،
    # ارتباط خبر قابل اتکاتر است.
    if (
        total_title_market_matches > 0
        and total_summary_market_matches > 0
    ):
        score += 2

    # -----------------------------------------------------
    # تصمیم اولیه برای عبور از فیلتر
    # -----------------------------------------------------

    has_direct_market = (
        total_title_market_matches > 0
        or total_summary_market_matches > 0
    )

    has_market_signal = len(signal_matches) > 0
    has_economic_driver = len(driver_matches) > 0
    has_major_event = len(major_event_matches) > 0

    # خبر مستقیم بازار، همراه با نشانه‌ای از تغییر،
    # تصمیم، تحلیل یا داده کاربردی.
    direct_market_with_signal = (
        has_direct_market
        and has_market_signal
    )

    # خبر مستقیم بازار که خلاصه نسبتاً معناداری دارد.
    direct_market_with_context = (
        has_direct_market
        and len(summary) >= 80
        and (
            has_economic_driver
            or has_major_event
            or len(market_matches) >= 1
        )
    )

    # رویداد مهم همراه با عامل اقتصادی و ارتباط بازار.
    event_with_economic_context = (
        has_major_event
        and has_economic_driver
        and has_direct_market
    )

    # عامل اقتصادی به تنهایی کافی نیست؛ باید به بازار هدف
    # ارتباط داشته باشد و نشانه یا زمینه خبری هم موجود باشد.
    economic_news_with_market_context = (
        has_direct_market
        and has_economic_driver
        and (
            has_market_signal
            or has_major_event
        )
    )

    include = any([
        direct_market_with_signal,
        direct_market_with_context,
        event_with_economic_context,
        economic_news_with_market_context,
    ])

    # امتیاز برای مراحل بعدی نگه داشته می‌شود؛
    # این عدد به‌تنهایی تضمین‌کننده اهمیت خبر نیست.
    return {
        "include": include,
        "score": score,
        "market_matches": market_matches,
        "title_market_matches": title_market_matches,
        "summary_market_matches": summary_market_matches,
        "driver_matches": driver_matches,
        "major_event_matches": major_event_matches,
        "signal_matches": signal_matches,
    }


# =========================================================
# اجرای فیلتر
# =========================================================

def main():
    print("===================================")
    print("ZarinMah Market News Filter")
    print("===================================")

    news = load_news()
    filtered_news = []

    rejected_count = 0

    for item in news:
        analysis = analyze_news(item)

        if not analysis["include"]:
            rejected_count += 1
            continue

        new_item = dict(item)

        new_item["market_score"] = analysis["score"]
        new_item["market_matches"] = analysis["market_matches"]
        new_item["title_market_matches"] = (
            analysis["title_market_matches"]
        )
        new_item["summary_market_matches"] = (
            analysis["summary_market_matches"]
        )
        new_item["driver_matches"] = analysis["driver_matches"]
        new_item["major_event_matches"] = (
            analysis["major_event_matches"]
        )
        new_item["signal_matches"] = analysis["signal_matches"]

        filtered_news.append(new_item)

    # امتیاز بالاتر ابتدا قرار می‌گیرد.
    filtered_news.sort(
        key=lambda item: item.get("market_score", 0),
        reverse=True,
    )

    save_filtered_news(filtered_news)

    print("Total news:", len(news))
    print("Accepted news:", len(filtered_news))
    print("Rejected news:", rejected_count)

    print()
    print("Top filtered news:")

    for item in filtered_news[:10]:
        print(
            "-",
            item.get("market_score", 0),
            "|",
            item.get("source", ""),
            "|",
            item.get("title", ""),
        )

    print()
    print("Saved:", FILTERED_FILE)


if __name__ == "__main__":
    main()
