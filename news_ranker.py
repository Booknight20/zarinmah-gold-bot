import json
import os
import re
import tempfile


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
        "حباب سکه",
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
        "تتر",
        "usd",
        "usdt",
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
        "کدال",
        "سهام",
        "بازار سهام",
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
    "مذاکرات هسته ای",
    "جنگ",
    "آتش‌بس",
    "آتش بس",
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
    "آمار",
    "داده",
    "گزارش",
    "روند",
    "سیگنال",
    "نرخ جدید",
    "اعلام شد",
]


# =========================================================
# ابزارهای متن
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
    text = text.replace("ـ", "")

    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def safe_int(value, default=0):
    try:
        if isinstance(value, bool):
            return default
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return default


def get_text(item, *keys):
    for key in keys:
        value = item.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def get_all_text_fields(item, *keys):
    """
    تمام فیلدهای متنی مرتبط را جمع می‌کند؛
    وجود یک فیلد نباید مانع بررسی فیلدهای دیگر شود.
    """
    result = []
    seen = set()

    for key in keys:
        value = item.get(key)

        if not isinstance(value, str) or not value.strip():
            continue

        normalized = normalize_text(value)

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        result.append(value.strip())

    return result


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
            f"{INPUT_FILE} must contain a JSON list. "
            "Output was not modified."
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
            prefix=".news_ranked_",
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


def keyword_pattern(keyword):
    normalized = normalize_text(keyword)

    if not normalized:
        return None

    parts = normalized.split()

    phrase = r"[\s\-_–—]*".join(
        re.escape(part) for part in parts
    )

    return (
        r"(?<!\w)"
        + phrase
        + r"(?:ی|ها|های)?"
        + r"(?!\w)"
    )


def find_matches(text, keywords):
    text = normalize_text(text)
    matches = []

    if not text:
        return matches

    for keyword in keywords:
        pattern = keyword_pattern(keyword)

        if pattern and re.search(pattern, text):
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
    وجود عدد را بررسی می‌کند.
    وجود عدد به‌تنهایی باعث انتشار خبر نمی‌شود.
    """
    text = normalize_text(text)

    return bool(
        re.search(r"\d+(?:[.,]\d+)?\s*%?", text)
    )


def get_original_filter_score(item):
    """
    امتیاز فیلتر را از امتیاز رتبه‌بندی جدا نگه می‌دارد.
    """
    if "filter_market_score" in item:
        return max(
            0,
            safe_int(item.get("filter_market_score"), 0),
        )

    # در خروجی قبلی رتبه‌بندی، market_score امتیاز نهایی است.
    if item.get("ranking_applied") is True:
        return 0

    return max(
        0,
        safe_int(item.get("market_score"), 0),
    )


# =========================================================
# رتبه‌بندی خبر
# =========================================================

def rank_news(item):
    title = normalize_text(
        get_text(item, "title", "headline")
    )

    summary = normalize_text(
        get_text(item, "summary", "description")
    )

    full_text_fields = get_all_text_fields(
        item,
        "full_text",
        "full_content",
        "content",
        "text",
    )

    # بررسی تمام متن‌های موجود، نه فقط اولین فیلد غیرخالی
    full_text = normalize_text(" ".join(full_text_fields))

    text = normalize_text(
        title + " " + summary + " " + full_text
    )

    # -----------------------------------------------------
    # تشخیص بازار
    # -----------------------------------------------------

    title_market_matches = {}
    summary_market_matches = {}
    full_text_market_matches = {}
    market_matches = {}

    for market_name, keywords in MARKET_KEYWORDS.items():
        title_matches = find_matches(title, keywords)
        summary_matches = find_matches(summary, keywords)
        full_text_matches = find_matches(full_text, keywords)

        combined = combine_matches(
            title_matches,
            summary_matches,
            full_text_matches,
        )

        if title_matches:
            title_market_matches[market_name] = title_matches

        if summary_matches:
            summary_market_matches[market_name] = summary_matches

        if full_text_matches:
            full_text_market_matches[market_name] = full_text_matches

        if combined:
            market_matches[market_name] = combined

    gold_matches = market_matches.get("gold", [])
    currency_matches = market_matches.get("currency", [])
    stock_matches = market_matches.get("stock", [])

    # -----------------------------------------------------
    # تشخیص عوامل اثرگذار
    # -----------------------------------------------------

    high_title_matches = find_matches(
        title, HIGH_IMPACT_KEYWORDS
    )
    high_summary_matches = find_matches(
        summary, HIGH_IMPACT_KEYWORDS
    )
    high_full_text_matches = find_matches(
        full_text, HIGH_IMPACT_KEYWORDS
    )

    medium_title_matches = find_matches(
        title, MEDIUM_IMPACT_KEYWORDS
    )
    medium_summary_matches = find_matches(
        summary, MEDIUM_IMPACT_KEYWORDS
    )
    medium_full_text_matches = find_matches(
        full_text, MEDIUM_IMPACT_KEYWORDS
    )

    signal_title_matches = find_matches(
        title, MARKET_SIGNAL_KEYWORDS
    )
    signal_summary_matches = find_matches(
        summary, MARKET_SIGNAL_KEYWORDS
    )
    signal_full_text_matches = find_matches(
        full_text, MARKET_SIGNAL_KEYWORDS
    )

    high_impact_matches = combine_matches(
        high_title_matches,
        high_summary_matches,
        high_full_text_matches,
    )

    medium_impact_matches = combine_matches(
        medium_title_matches,
        medium_summary_matches,
        medium_full_text_matches,
    )

    signal_matches = combine_matches(
        signal_title_matches,
        signal_summary_matches,
        signal_full_text_matches,
    )

    # -----------------------------------------------------
    # محاسبه امتیاز رتبه‌بندی
    # -----------------------------------------------------

    score = 0

    # عنوان وزن بیشتری دارد.
    score += sum(
        len(matches) * 4
        for matches in title_market_matches.values()
    )

    # خلاصه وزن متوسط دارد.
    score += sum(
        len(matches) * 2
        for matches in summary_market_matches.values()
    )

    # متن کامل وزن کمتری دارد و امتیاز آن محدود است.
    full_text_market_count = sum(
        len(matches)
        for matches in full_text_market_matches.values()
    )
    score += min(full_text_market_count, 6)

    score += min(len(high_impact_matches), 8) * 4
    score += min(len(medium_impact_matches), 8) * 2
    score += min(len(signal_matches), 4)

    has_numeric_evidence = count_numeric_evidence(text)

    if has_numeric_evidence:
        score += 2

    market_count = sum(
        bool(market_matches.get(market))
        for market in ("gold", "currency", "stock")
    )

    if market_count >= 2:
        score += 4

    if title_market_matches and summary_market_matches:
        score += 2

    # -----------------------------------------------------
    # امتیاز مرحله فیلتر
    # -----------------------------------------------------

    previous_filter_score = get_original_filter_score(item)

    # امتیاز فیلتر فقط کمک محدود می‌کند تا بر رتبه‌بندی مسلط نشود.
    filter_score_bonus = min(previous_filter_score, 6)
    score += filter_score_bonus

    # -----------------------------------------------------
    # تعیین اولویت
    # -----------------------------------------------------

    has_market = bool(market_matches)
    has_high_impact = bool(high_impact_matches)
    has_signal = bool(signal_matches)

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
    # دلایل امتیازدهی
    # -----------------------------------------------------

    reasons = []

    if title_market_matches:
        reasons.append("ارتباط بازار در عنوان")

    if summary_market_matches:
        reasons.append("ارتباط بازار در خلاصه")

    if full_text_market_matches:
        reasons.append("ارتباط بازار در متن کامل")

    if high_impact_matches:
        reasons.append("عامل پراثر اقتصادی یا سیاسی")

    if medium_impact_matches:
        reasons.append("عامل اقتصادی")

    if signal_matches:
        reasons.append("نشانه اطلاعات کاربردی بازار")

    if has_numeric_evidence:
        reasons.append("وجود عدد در متن")

    if market_count >= 2:
        reasons.append("ارتباط با چند بازار")

    if filter_score_bonus:
        reasons.append("امتیاز کمکی مرحله فیلتر")

    if not has_market:
        reasons.append("بازار هدف مشخصی شناسایی نشد")

    return {
        "market_score": score,
        "priority": priority,

        "filter_market_score": previous_filter_score,
        "filter_score_bonus": filter_score_bonus,

        "gold_matches": gold_matches,
        "currency_matches": currency_matches,
        "stock_matches": stock_matches,
        "market_matches": market_matches,

        "title_market_matches": title_market_matches,
        "summary_market_matches": summary_market_matches,
        "full_text_market_matches": full_text_market_matches,

        "high_impact_matches": high_impact_matches,
        "medium_impact_matches": medium_impact_matches,
        "signal_matches": signal_matches,

        "has_numeric_evidence": has_numeric_evidence,
        "market_count": market_count,
        "ranking_reasons": reasons,
        "ranking_applied": True,
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
        new_item = dict(item)

        original_filter_score = get_original_filter_score(
            new_item
        )

        new_item["filter_market_score"] = original_filter_score

        analysis = rank_news(new_item)
        new_item.update(analysis)

        ranked_news.append(new_item)

    ranked_news.sort(
        key=lambda item: safe_int(
            item.get("market_score", 0),
            0,
        ),
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
            get_text(item, "title", "headline"),
        )

    print()
    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
