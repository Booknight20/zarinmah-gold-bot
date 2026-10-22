import json
import os
import re
import tempfile


# =========================================================
# تنظیمات
# =========================================================

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
        "حباب سکه",
        "صندوق طلا",
        "صندوق های طلا",
        "صندوق‌های طلا",
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
        "کدال",
        "سهام",
        "شاخص کل بورس",
        "بازار سهام",
        "معاملات سهام",
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
    "عرضه ارز",
    "تقاضای ارز",
    "کسری تجاری",
    "حجم نقدینگی",
    "سیاست مالی",
    "نرخ سپرده",
    "نرخ سود",
    "بازده اوراق قرضه",
    "تصمیم فدرال رزرو",
    "سیاست تجاری",
    "قیمت جهانی نفت",
    "واردات",
    "صادرات",
    "ترازنامه بانک مرکزی",
]


# =========================================================
# رویدادهای سیاسی و منطقه‌ای
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
    "تحریم اقتصادی",
    "مذاکرات سیاسی",
    "توافق هسته‌ای",
    "توافق هسته ای",
    "ریسک ژئوپلیتیک",
    "ریسک سیاسی",
    "تنش بین ایران و اسرائیل",
    "ایران و اسرائیل",
]


# =========================================================
# نشانه‌های خبر، تغییر، داده یا تحلیل
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
    "اعلام کرد",
    "اعلام شد",
    "منتشر شد",
    "گزارش",
    "داده",
    "آمار",
    "هدف",
    "پیشروی",
    "عقب‌نشینی",
    "عقب نشینی",
    "روند",
    "سیگنال",
    "ورود نقدینگی",
    "خروج نقدینگی",
    "ارزش معاملات",
    "سیاست جدید",
    "نرخ جدید",
    "تغییر نرخ",
]


# =========================================================
# الگوهای تبلیغاتی آشکار
# =========================================================

PROMOTIONAL_PATTERNS = [
    r"عضویت\s+در\s+کانال",
    r"برای\s+تبلیغات\s+پیام\s+دهید",
    r"تبلیغات\s+پذیرفته\s+می\s+شود",
    r"فروش\s+ویژه\s+دوره",
    r"ثبت\s+نام\s+دوره\s+آموزشی",
    r"مشاوره\s+رایگان\s+خرید",
    r"برای\s+خرید\s+به\s+این\s+آیدی",
    r"کسب\s+درآمد\s+تضمینی",
    r"سود\s+تضمینی",
    r"سیگنال\s+تضمینی",
    r"بدون\s+ریسک",
]


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

    # یکسان‌سازی فاصله‌ها و نیم‌فاصله
    text = text.replace("\u200c", " ")
    text = text.replace("\u200f", " ")
    text = text.replace("\u200e", " ")
    text = text.replace("\ufeff", " ")
    text = text.replace("\xa0", " ")

    # یکسان‌سازی بعضی نشانه‌های نگارشی
    text = text.replace("ـ", "")
    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def get_item_text(item, *keys):
    """اولین متن غیرخالی از میان فیلدهای مشخص‌شده."""
    for key in keys:
        value = item.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def build_searchable_text(item):
    """عنوان، خلاصه و متن کامل خبر را برای جست‌وجو ترکیب می‌کند."""
    fields = [
        get_item_text(item, "title", "headline"),
        get_item_text(item, "summary", "description"),
        get_item_text(item, "full_text"),
        get_item_text(item, "full_content"),
        get_item_text(item, "content"),
        get_item_text(item, "text"),
    ]

    unique_fields = []
    seen = set()

    for field in fields:
        normalized = normalize_text(field)

        if normalized and normalized not in seen:
            unique_fields.append(field)
            seen.add(normalized)

    return unique_fields


# =========================================================
# خواندن و ذخیره امن فایل‌ها
# =========================================================

def load_news():
    if not os.path.exists(NEWS_FILE):
        raise FileNotFoundError(
            f"فایل ورودی پیدا نشد: {NEWS_FILE}. "
            "برای جلوگیری از حذف ناخواسته خبرها، خروجی ساخته نشد."
        )

    try:
        with open(NEWS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"JSON ورودی خراب است؛ خروجی تغییر نکرد: {error}"
        ) from error

    if not isinstance(data, list):
        raise ValueError(
            "ساختار news_items.json باید یک فهرست JSON باشد؛ "
            "خروجی تغییر نکرد."
        )

    invalid_count = sum(
        1 for item in data if not isinstance(item, dict)
    )

    if invalid_count:
        print(
            "Warning: invalid non-object records skipped:",
            invalid_count,
        )

    return [
        item for item in data
        if isinstance(item, dict)
    ]


def save_filtered_news(news):
    directory = os.path.dirname(os.path.abspath(FILTERED_FILE))

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix=".news_filtered_",
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

        os.replace(temp_path, FILTERED_FILE)

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


# =========================================================
# جست‌وجوی عبارت‌ها با تحمل تفاوت فاصله
# =========================================================

def keyword_pattern(keyword):
    normalized = normalize_text(keyword)

    if not normalized:
        return None

    parts = normalized.split()

    # عباراتی مانند «نیم‌سکه» و «نیم سکه» یکسان بررسی می‌شوند.
    phrase = r"[\s\-_–—]*".join(
        re.escape(part) for part in parts
    )

    # اجازه به پسوندهای رایج، بدون پذیرش هر زیررشته‌ای
    return (
        r"(?<!\w)"
        + phrase
        + r"(?:ی|ها|های)?"
        + r"(?!\w)"
    )


def find_matches(text, keywords):
    normalized_text = normalize_text(text)
    matches = []

    if not normalized_text:
        return matches

    for keyword in keywords:
        pattern = keyword_pattern(keyword)

        if pattern and re.search(pattern, normalized_text):
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
# تشخیص تبلیغات آشکار
# =========================================================

def is_obvious_promotion(text):
    normalized = normalize_text(text)

    matched_patterns = []

    for pattern in PROMOTIONAL_PATTERNS:
        if re.search(pattern, normalized):
            matched_patterns.append(pattern)

    # یک عبارت تبلیغاتی به‌تنهایی برای رد کافی نیست؛
    # برای کاهش حذف اشتباه خبر، دو نشانه مستقل لازم است.
    return len(matched_patterns) >= 2, matched_patterns


# =========================================================
# تحلیل ارتباط و ارزش اولیه خبر
# =========================================================

def analyze_news(item):
    title_raw = get_item_text(item, "title", "headline")
    summary_raw = get_item_text(item, "summary", "description")

    title = normalize_text(title_raw)
    summary = normalize_text(summary_raw)

    all_fields = build_searchable_text(item)
    full_text = normalize_text(" ".join(all_fields))

    if not title and not summary and not full_text:
        return {
            "include": False,
            "score": 0,
            "reason": "empty_content",
            "market_matches": {},
            "title_market_matches": {},
            "summary_market_matches": {},
            "driver_matches": [],
            "major_event_matches": [],
            "signal_matches": [],
            "full_text_market_matches": {},
        }

    market_matches = {}
    title_market_matches = {}
    summary_market_matches = {}
    full_text_market_matches = {}

    total_title_market_matches = 0
    total_summary_market_matches = 0
    total_full_text_market_matches = 0

    for market_name, keywords in MARKET_KEYWORDS.items():
        title_matches = find_matches(title, keywords)
        summary_matches = find_matches(summary, keywords)
        all_text_matches = find_matches(full_text, keywords)

        combined_matches = unique_matches(
            title_matches,
            summary_matches,
            all_text_matches,
        )

        if combined_matches:
            market_matches[market_name] = combined_matches

        if title_matches:
            title_market_matches[market_name] = title_matches
            total_title_market_matches += len(title_matches)

        if summary_matches:
            summary_market_matches[market_name] = summary_matches
            total_summary_market_matches += len(summary_matches)

        if all_text_matches:
            full_text_market_matches[market_name] = all_text_matches
            total_full_text_market_matches += len(all_text_matches)

    driver_matches = find_matches(
        full_text,
        ECONOMIC_DRIVER_KEYWORDS,
    )

    major_event_matches = find_matches(
        full_text,
        MAJOR_EVENT_KEYWORDS,
    )

    title_signal_matches = find_matches(
        title,
        MARKET_SIGNAL_KEYWORDS,
    )

    summary_signal_matches = find_matches(
        summary,
        MARKET_SIGNAL_KEYWORDS,
    )

    all_signal_matches = find_matches(
        full_text,
        MARKET_SIGNAL_KEYWORDS,
    )

    signal_matches = unique_matches(
        title_signal_matches,
        summary_signal_matches,
        all_signal_matches,
    )

    # -----------------------------------------------------
    # امتیاز اولیه
    # -----------------------------------------------------

    score = 0

    # عنوان وزن بالاتری دارد.
    score += total_title_market_matches * 4

    # خلاصه وزن متوسط دارد.
    score += total_summary_market_matches * 2

    # متن کامل برای کشف ارتباط مفید است؛
    # برای جلوگیری از تورم امتیاز، فقط چند تطبیق امتیاز می‌گیرند.
    score += min(total_full_text_market_matches, 6)

    score += min(len(driver_matches), 6) * 2
    score += min(len(major_event_matches), 5) * 2
    score += min(len(signal_matches), 5)

    if len(market_matches) >= 2:
        score += 3

    if total_title_market_matches and total_summary_market_matches:
        score += 2

    if title and summary and len(summary) >= 100:
        score += 1

    # -----------------------------------------------------
    # تصمیم عبور از فیلتر
    # -----------------------------------------------------

    has_direct_market = bool(market_matches)
    has_market_signal = bool(signal_matches)
    has_economic_driver = bool(driver_matches)
    has_major_event = bool(major_event_matches)

    # خبر مستقیم بازار همراه با نشانه تغییر، تحلیل یا داده.
    direct_market_with_signal = (
        has_direct_market and has_market_signal
    )

    # خبر مستقیم با زمینه متنی قابل قبول.
    direct_market_with_context = (
        has_direct_market
        and len(summary) >= 80
    )

    # خبر اقتصادی یا سیاسی که اثر بالقوه بین‌بازاری دارد؛
    # وجود عامل اقتصادی و ارتباط روشن با بازار هدف ضروری است.
    event_with_economic_context = (
        has_major_event
        and has_economic_driver
        and has_direct_market
    )

    economic_news_with_market_context = (
        has_direct_market
        and has_economic_driver
        and (
            has_market_signal
            or has_major_event
            or len(summary) >= 100
        )
    )

    include = any([
        direct_market_with_signal,
        direct_market_with_context,
        event_with_economic_context,
        economic_news_with_market_context,
    ])

    promotion_text = " ".join([
        title_raw,
        summary_raw,
        " ".join(all_fields),
    ])

    is_promotion, promotion_matches = is_obvious_promotion(
        promotion_text
    )

    if is_promotion:
        include = False
        reason = "obvious_promotion"
    elif include:
        reason = "relevant_market_news"
    elif not has_direct_market:
        reason = "no_target_market_match"
    else:
        reason = "insufficient_context_or_signal"

    return {
        "include": include,
        "score": score,
        "reason": reason,
        "market_matches": market_matches,
        "title_market_matches": title_market_matches,
        "summary_market_matches": summary_market_matches,
        "full_text_market_matches": full_text_market_matches,
        "driver_matches": driver_matches,
        "major_event_matches": major_event_matches,
        "signal_matches": signal_matches,
        "promotion_matches": promotion_matches,
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
    rejected_reasons = {}

    for item in news:
        analysis = analyze_news(item)

        if not analysis["include"]:
            reason = analysis.get("reason", "unknown")
            rejected_reasons[reason] = (
                rejected_reasons.get(reason, 0) + 1
            )
            continue

        new_item = dict(item)

        # امتیاز اولیه فیلتر جدا نگه داشته می‌شود تا
        # news_ranker.py آن را با امتیاز رتبه‌بندی اشتباه نگیرد.
        new_item["filter_market_score"] = analysis["score"]
        new_item["market_score"] = analysis["score"]

        new_item["market_matches"] = analysis["market_matches"]
        new_item["title_market_matches"] = (
            analysis["title_market_matches"]
        )
        new_item["summary_market_matches"] = (
            analysis["summary_market_matches"]
        )
        new_item["full_text_market_matches"] = (
            analysis["full_text_market_matches"]
        )
        new_item["driver_matches"] = analysis["driver_matches"]
        new_item["major_event_matches"] = (
            analysis["major_event_matches"]
        )
        new_item["signal_matches"] = analysis["signal_matches"]

        new_item["filter_reason"] = analysis["reason"]
        new_item["filter_applied"] = True

        filtered_news.append(new_item)

    # امتیاز اولیه بالاتر در ابتدای فهرست قرار می‌گیرد.
    filtered_news.sort(
        key=lambda item: item.get("filter_market_score", 0),
        reverse=True,
    )

    save_filtered_news(filtered_news)

    print("Total news:", len(news))
    print("Accepted news:", len(filtered_news))
    print("Rejected news:", len(news) - len(filtered_news))

    if rejected_reasons:
        print()
        print("Rejected reasons:")

        for reason, count in sorted(rejected_reasons.items()):
            print(f"- {reason}: {count}")

    print()
    print("Top filtered news:")

    for item in filtered_news[:10]:
        print(
            "-",
            item.get("filter_market_score", 0),
            "|",
            item.get("source", ""),
            "|",
            get_item_text(item, "title", "headline"),
        )

    print()
    print("Saved:", FILTERED_FILE)


if __name__ == "__main__":
    main()
