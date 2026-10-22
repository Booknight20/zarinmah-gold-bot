import html
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


# =========================================================
# تنظیمات
# =========================================================

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

OUTPUT_FILE = "analyst_ready.json"
SEEN_FILE = "analyst_seen.json"

# فقط کانال‌های تأییدشده بررسی می‌شوند.
ANALYSTS = {
    "پیام الیاس کردی": {"channel": "Payamelyaskordi"},
    "دکتر آرش امینی": {"channel": "drarashamini"},
    "حسین نصیری": {"channel": "nasiirry"},
    "علیرضا محرابی": {"channel": "AlirezaMehrabi_ir"},
    "ره‌آورد ۳۶۵": {"channel": "rahavard365"},
}

REQUEST_TIMEOUT = 30
MAX_SEEN_POSTS_PER_SOURCE = 3000


# =========================================================
# واژه‌های مرتبط با بازار
# =========================================================

MARKET_KEYWORDS = [
    "طلا", "طلای ۱۸", "طلای 18", "طلای ۲۴", "طلای 24",
    "طلای آبشده", "آبشده", "اونس", "اونس جهانی",
    "سکه", "سکه امامی", "نیم سکه", "نیم‌سکه",
    "ربع سکه", "ربع‌سکه", "حباب طلا", "حباب سکه",
    "دلار", "دلار آزاد", "ارز", "نرخ ارز", "بازار ارز",
    "یورو", "درهم", "پوند", "ریال", "مرکز مبادله",
    "دلار محاسباتی", "بورس", "بازار سرمایه", "شاخص",
    "شاخص کل", "شاخص کل بورس", "شاخص هم وزن",
    "شاخص هم‌وزن", "فرابورس", "نماد", "ارزش معاملات",
    "ارزش بازار", "عرضه اولیه", "ورود پول حقیقی",
    "خروج پول حقیقی", "پول حقیقی", "پول هوشمند",
    "جریان نقدینگی", "نقدینگی", "صندوق طلا",
    "صندوق‌های طلا", "صندوق نقره", "صندوق‌های نقره",
    "گواهی سپرده", "گواهی سپرده شمش", "نرخ بهره",
    "فدرال رزرو", "تورم", "بانک مرکزی", "سیاست پولی",
    "سیاست ارزی", "پایه پولی", "کسری بودجه",
    "رشد اقتصادی", "رکود", "قیمت نفت", "نفت",
    "تحریم", "اوراق", "بازده اوراق", "بازدهی",
    "ارزش ذاتی", "حباب صندوق", "تتر", "بیت کوین",
    "بیت‌کوین", "کریپتو", "رمزارز", "شاخص دلار",
    "بازده اوراق آمریکا", "نرخ بهره آمریکا",
]


# =========================================================
# واژه‌های تحلیل و سیگنال
# =========================================================

ANALYSIS_KEYWORDS = [
    "تحلیل", "پیش بینی", "پیش‌بینی", "سناریو",
    "احتمال", "انتظار", "انتظارات", "چشم انداز",
    "چشم‌انداز", "روند", "مسیر", "هدف", "اهداف",
    "حمایت", "مقاومت", "شکست", "اصلاح", "رشد",
    "افزایش", "کاهش", "صعود", "نزول", "ریزش",
    "صعودی", "نزولی", "معامله", "خرید", "فروش",
    "ورود", "خروج", "ریسک", "بازده", "ارزش گذاری",
    "ارزش‌گذاری", "بنیادی", "تکنیکال", "تکنیکالی",
    "نقدینگی", "جریان پول", "عرضه", "تقاضا",
    "نرخ", "قیمت", "حباب", "تثبیت", "محدوده",
    "واگرایی", "همگرایی", "شکاف", "تغییر روند",
    "میانگین متحرک", "حجم معاملات", "قدرت خریدار",
    "قدرت فروشنده", "پول هوشمند", "نقطه ورود",
    "حد ضرر", "حد سود", "ارزش ذاتی",
]


# =========================================================
# نشانه‌های تبلیغاتی
# =========================================================

PROMOTIONAL_KEYWORDS = [
    "ثبت نام", "ثبت‌نام", "دوره آموزشی",
    "وبینار", "پکیج آموزشی", "مشاوره اختصاصی",
    "فروش ویژه", "کد تخفیف", "عضویت ویژه",
    "اشتراک ویژه", "خرید اشتراک", "خرید دوره",
    "فروش دوره", "لینک ثبت نام", "لینک ثبت‌نام",
    "ظرفیت محدود", "همین حالا ثبت نام",
    "همین حالا ثبت‌نام", "تبلیغات پذیرفته می‌شود",
    "تبلیغات پذیرفته میشود", "جهت تبلیغات",
    "برای تبلیغات تماس", "سود تضمینی",
    "سیگنال تضمینی", "درآمد تضمینی",
]


CALL_TO_ACTION_KEYWORDS = [
    "ثبت نام", "ثبت‌نام", "عضو شوید",
    "عضویت", "همین حالا بخرید", "خرید دوره",
    "خرید اشتراک", "لینک خرید", "جهت ثبت نام",
    "جهت ثبت‌نام", "برای اطلاعات بیشتر تماس",
    "دایرکت دهید", "پیام دهید برای خرید",
]


# =========================================================
# زمان
# =========================================================

def now_iso():
    return datetime.now(TEHRAN_TZ).isoformat()


# =========================================================
# پاک‌سازی و نرمال‌سازی متن
# =========================================================

def clean_html(text):
    if not text:
        return ""

    text = str(text)

    text = re.sub(
        r"<br\s*/?>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"</p\s*>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"</div\s*>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = html.unescape(text)

    text = text.replace("\u200f", "")
    text = text.replace("\u200e", "")
    text = text.replace("\ufeff", "")
    text = text.replace("\u00a0", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n[ \t]*\n{2,}",
        "\n\n",
        text,
    )

    return text.strip()


def normalize(text):
    text = str(text or "")

    text = (
        text.replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ك", "ک")
        .replace("ة", "ه")
        .replace("ۀ", "ه")
        .replace("\u200c", " ")
        .replace("\u200f", "")
        .replace("\u200e", "")
        .lower()
    )

    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"

    for index, digit in enumerate(persian_digits):
        text = text.replace(digit, str(index))

    for index, digit in enumerate(arabic_digits):
        text = text.replace(digit, str(index))

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================================================
# مدیریت فایل‌ها
# =========================================================

def load_seen():
    default = {"sources": {}}

    if not os.path.exists(SEEN_FILE):
        return default

    try:
        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return default

        data.setdefault("sources", {})

        if not isinstance(data["sources"], dict):
            data["sources"] = {}

        return data

    except Exception as error:
        print("Could not load seen data:", error)
        return default


def save_seen(data):
    temporary_file = SEEN_FILE + ".tmp"

    with open(
        temporary_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(temporary_file, SEEN_FILE)


def save_ready(data):
    temporary_file = OUTPUT_FILE + ".tmp"

    with open(
        temporary_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(temporary_file, OUTPUT_FILE)


# =========================================================
# دریافت پست‌های عمومی تلگرام
# =========================================================

def fetch_channel(channel):
    url = f"https://t.me/s/{channel}"

    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; ZarinMahBot/1.0; "
                "+https://t.me/ZarinMahGold)"
            )
        },
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    pattern = re.compile(
        r'<a class="tgme_widget_message_date[^"]*"'
        r'\s+href="([^"]+)"[^>]*>.*?</a>'
        r".*?"
        r'<div class="tgme_widget_message_text[^"]*"'
        r'[^>]*>(.*?)</div>',
        re.DOTALL,
    )

    posts = []

    for match in pattern.finditer(response.text):
        link = html.unescape(match.group(1)).strip()
        raw_text = match.group(2)
        text = clean_html(raw_text)

        if not link or not text:
            continue

        posts.append({
            "link": link,
            "text": text,
        })

    # حذف لینک‌های تکراری با حفظ ترتیب دریافت
    unique = []
    seen_links = set()

    for post in posts:
        if post["link"] in seen_links:
            continue

        seen_links.add(post["link"])
        unique.append(post)

    return unique


# =========================================================
# تطبیق کلیدواژه‌ها
# =========================================================

def find_matches(text, keywords):
    normalized_text = normalize(text)
    matches = []

    for keyword in keywords:
        normalized_keyword = normalize(keyword)

        if normalized_keyword and normalized_keyword in normalized_text:
            matches.append(keyword)

    return list(dict.fromkeys(matches))


# =========================================================
# تشخیص تبلیغات
# =========================================================

def is_promotional(text):
    normalized_text = normalize(text)

    promo_matches = find_matches(
        normalized_text,
        PROMOTIONAL_KEYWORDS,
    )

    cta_matches = find_matches(
        normalized_text,
        CALL_TO_ACTION_KEYWORDS,
    )

    market_matches = find_matches(
        normalized_text,
        MARKET_KEYWORDS,
    )

    analysis_matches = find_matches(
        normalized_text,
        ANALYSIS_KEYWORDS,
    )

    # یک کلمه مانند «خرید» یا «مشاوره» به‌تنهایی
    # برای رد تحلیل کافی نیست.
    #
    # تبلیغ وقتی رد می‌شود که نشانه‌های تبلیغاتی
    # و دعوت به اقدام وجود داشته باشد و محتوای
    # تحلیلی قابل‌توجهی ارائه نشده باشد.

    strong_promo_matches = [
        phrase
        for phrase in promo_matches
        if normalize(phrase) in {
            normalize("خرید دوره"),
            normalize("فروش دوره"),
            normalize("پکیج آموزشی"),
            normalize("سود تضمینی"),
            normalize("سیگنال تضمینی"),
            normalize("درآمد تضمینی"),
            normalize("اشتراک ویژه"),
            normalize("خرید اشتراک"),
            normalize("کد تخفیف"),
        }
    ]

    if strong_promo_matches:
        if len(analysis_matches) < 3:
            return True

    if (
        len(promo_matches) >= 2
        and len(cta_matches) >= 1
        and len(analysis_matches) < 3
        and len(market_matches) < 5
    ):
        return True

    # تبلیغ کوتاه و بدون محتوای تحلیلی
    if (
        len(normalized_text) < 500
        and len(cta_matches) >= 2
        and len(analysis_matches) < 2
    ):
        return True

    return False


# =========================================================
# ارزیابی کیفیت تحلیل
# =========================================================

def has_numeric_evidence(text):
    normalized_text = normalize(text)

    # عدد یا درصد به‌تنهایی اثبات کیفیت نیست؛
    # فقط یک نشانه کمکی در امتیازدهی است.
    return bool(
        re.search(
            r"\d+(?:[.,]\d+)?\s*%?",
            normalized_text,
        )
    )


def has_reasoning_structure(text):
    normalized_text = normalize(text)

    reasoning_patterns = [
        "به دلیل",
        "زیرا",
        "در نتیجه",
        "بنابراین",
        "اگر",
        "در صورتی که",
        "از طرفی",
        "با توجه به",
        "عامل اصلی",
        "علت این",
        "ناشی از",
        "در مقابل",
        "اما اگر",
        "مشروط به",
        "به شرط",
    ]

    return any(
        normalize(pattern) in normalized_text
        for pattern in reasoning_patterns
    )


def evaluate_analysis(text):
    text = clean_html(text)
    normalized_text = normalize(text)

    market_matches = find_matches(
        normalized_text,
        MARKET_KEYWORDS,
    )

    analysis_matches = find_matches(
        normalized_text,
        ANALYSIS_KEYWORDS,
    )

    score = 0
    reasons = []

    # ارتباط با بازار
    score += min(len(market_matches), 8) * 2

    if market_matches:
        reasons.append("ارتباط با بازار")

    # وجود دیدگاه، پیش‌بینی، روند یا تصمیم تحلیلی
    score += min(len(analysis_matches), 6) * 2

    if analysis_matches:
        reasons.append("دارای نشانه‌های تحلیل")

    # متن طولانی‌تر فقط امتیاز کمکی می‌گیرد؛
    # طول به‌تنهایی به معنی کیفیت نیست.
    if len(text) >= 250:
        score += 1
        reasons.append("دارای توضیح")

    if len(text) >= 700:
        score += 1

    # وجود عدد می‌تواند به مشخص‌تر بودن تحلیل کمک کند.
    if has_numeric_evidence(text):
        score += 2
        reasons.append("دارای داده عددی")

    # وجود رابطه علت و معلولی
    if has_reasoning_structure(text):
        score += 3
        reasons.append("دارای استدلال")

    # تحلیل‌هایی که به چند حوزه بازار می‌پردازند
    # ممکن است ارزش اطلاعاتی بیشتری داشته باشند.
    market_groups = {
        "gold": [
            "طلا", "آبشده", "اونس", "سکه",
        ],
        "currency": [
            "دلار", "ارز", "یورو", "درهم", "تتر",
        ],
        "stock": [
            "بورس", "شاخص", "نماد", "فرابورس",
            "صندوق", "ارزش معاملات",
        ],
        "economy": [
            "تورم", "نرخ بهره", "بانک مرکزی",
            "نفت", "تحریم", "کسری بودجه",
        ],
    }

    matched_groups = []

    for group_name, keywords in market_groups.items():
        if any(
            normalize(keyword) in normalized_text
            for keyword in keywords
        ):
            matched_groups.append(group_name)

    if len(matched_groups) >= 2:
        score += 3
        reasons.append("ارتباط میان چند حوزه بازار")

    if is_promotional(text):
        return {
            "relevant": False,
            "score": score,
            "market_matches": market_matches,
            "analysis_matches": analysis_matches,
            "market_groups": matched_groups,
            "reasons": reasons,
            "reject_reason": "promotional",
        }

    # شرط ارتباط مستقیم با بازار ضروری است.
    if not market_matches:
        return {
            "relevant": False,
            "score": score,
            "market_matches": [],
            "analysis_matches": analysis_matches,
            "market_groups": matched_groups,
            "reasons": reasons,
            "reject_reason": "no_market_evidence",
        }

    # تحلیل دارای دیدگاه یا استدلال می‌تواند حتی
    # بدون تعداد زیادی کلیدواژه پذیرفته شود.
    has_analysis = bool(analysis_matches)
    has_reasoning = has_reasoning_structure(text)
    has_sufficient_length = len(text) >= 180

    relevant = (
        (score >= 8 and has_analysis)
        or (
            score >= 7
            and has_reasoning
            and has_sufficient_length
        )
        or (
            len(market_matches) >= 2
            and has_analysis
            and len(text) >= 120
        )
    )

    if not relevant:
        reject_reason = "insufficient_analysis_evidence"
    else:
        reject_reason = ""

    return {
        "relevant": relevant,
        "score": score,
        "market_matches": market_matches,
        "analysis_matches": analysis_matches,
        "market_groups": matched_groups,
        "reasons": reasons,
        "reject_reason": reject_reason,
    }


def is_relevant(text):
    """
    سازگاری با نام تابع قبلی.
    """
    result = evaluate_analysis(text)

    return (
        result["relevant"],
        result["score"],
        result["market_matches"],
    )


# =========================================================
# ساخت عنوان و محتوای تحلیل
# =========================================================

def build_title(text):
    lines = [
        line.strip()
        for line in clean_html(text).splitlines()
        if line.strip()
    ]

    if lines:
        first = lines[0]

        if len(first) <= 120 and not first.startswith("@"):
            return first

    sentences = re.split(
        r"(?<=[.!؟؛])\s+",
        clean_html(text),
    )

    if sentences:
        title = sentences[0].strip()

        if len(title) > 120:
            title = title[:117].rstrip() + "..."

        if title:
            return title

    return "تحلیل جدید بازار"


def build_summary(text):
    """
    متن کامل در دسترس از منبع را حفظ می‌کند.
    هیچ سقف ۹۰۰ نویسه‌ای یا محدودیت تعداد جمله ندارد.

    بخش‌بندی متن‌های بلند در مرحله انتشار انجام می‌شود.
    """

    return clean_html(text)


def make_item(source_name, post, evaluation):
    original_text = clean_html(post.get("text", ""))

    title = build_title(original_text)
    full_text = original_text

    # summary برای سازگاری با ناشر قبلی باقی می‌ماند،
    # اما اکنون متن کامل تحلیل را نگه می‌دارد.
    summary = build_summary(original_text)

    score = evaluation["score"]

    return {
        "analyst": source_name,
        "title": title,
        "summary": summary,
        "full_text": full_text,
        "source": source_name,
        "link": post["link"],
        "analysis_score": score,
        "market_matches": evaluation["market_matches"],
        "analysis_matches": evaluation["analysis_matches"],
        "market_groups": evaluation["market_groups"],
        "analysis_reasons": evaluation["reasons"],
        "priority": "high" if score >= 12 else "medium",
        "content_length": len(full_text),
        "content_complete_from_source": True,
        "collected_at": now_iso(),
    }


# =========================================================
# مدیریت پست‌های دیده‌شده
# =========================================================

def initialize_source(seen, source_name, posts):
    """
    در اولین اجرا، پست‌های موجود به‌عنوان آرشیو ثبت می‌شوند
    و منتشر نمی‌شوند؛ برای جلوگیری از انتشار انبوه آرشیو.
    """

    sources = seen.setdefault("sources", {})

    if source_name in sources:
        return False

    post_ids = [
        post["link"]
        for post in posts
        if post.get("link")
    ]

    sources[source_name] = {
        "initialized_at": now_iso(),
        "post_ids": list(dict.fromkeys(post_ids))[
            -MAX_SEEN_POSTS_PER_SOURCE:
        ],
    }

    print("Initialized source:", source_name)
    print(
        "Existing posts registered:",
        len(sources[source_name]["post_ids"]),
    )

    return True


def source_has_post(seen, source_name, post_id):
    sources = seen.setdefault("sources", {})

    source_data = sources.setdefault(
        source_name,
        {
            "initialized_at": now_iso(),
            "post_ids": [],
        },
    )

    return post_id in source_data.get("post_ids", [])


def mark_source_post(seen, source_name, post_id):
    sources = seen.setdefault("sources", {})

    source_data = sources.setdefault(
        source_name,
        {
            "initialized_at": now_iso(),
            "post_ids": [],
        },
    )

    post_ids = source_data.setdefault("post_ids", [])

    if post_id not in post_ids:
        post_ids.append(post_id)

    source_data["post_ids"] = list(
        dict.fromkeys(post_ids)
    )[-MAX_SEEN_POSTS_PER_SOURCE:]


# =========================================================
# اجرای اصلی
# =========================================================

def main():
    print("===================================")
    print("ZarinMah Analyst Collector")
    print("===================================")

    seen = load_seen()
    ready = []

    for source_name, config in ANALYSTS.items():
        print("\nReading:", source_name)

        try:
            posts = fetch_channel(config["channel"])

        except Exception as error:
            print(
                "Channel error:",
                source_name,
                error,
            )
            continue

        print("Posts found:", len(posts))

        if initialize_source(
            seen,
            source_name,
            posts,
        ):
            continue

        for post in posts:
            post_id = post.get("link")

            if not post_id:
                continue

            if source_has_post(
                seen,
                source_name,
                post_id,
            ):
                continue

            text = clean_html(post.get("text", ""))

            if not text:
                mark_source_post(
                    seen,
                    source_name,
                    post_id,
                )
                continue

            evaluation = evaluate_analysis(text)

            if not evaluation["relevant"]:
                print(
                    "Skipped:",
                    source_name,
                    "|",
                    evaluation["reject_reason"],
                    "| score:",
                    evaluation["score"],
                )

                # پست نامرتبط فعلاً در فهرست دیده‌شده ثبت نمی‌شود.
                # در اجرای بعد، در صورت تغییر معیارها می‌تواند
                # دوباره ارزیابی شود.
                continue

            item = make_item(
                source_name,
                post,
                evaluation,
            )

            ready.append(item)

            # فقط پس از پذیرش تحلیل، شناسه ثبت می‌شود.
            mark_source_post(
                seen,
                source_name,
                post_id,
            )

            print(
                "Accepted:",
                source_name,
                "| score:",
                evaluation["score"],
                "| length:",
                len(text),
                "|",
                item["title"],
            )

    save_seen(seen)

    # تحلیل‌های با امتیاز بالاتر زودتر منتشر می‌شوند.
    # هیچ سقف تعدادی برای تحلیل‌های آماده وجود ندارد.
    ready.sort(
        key=lambda item: item.get("analysis_score", 0),
        reverse=True,
    )

    save_ready(ready)

    print("\nNew relevant analyses:", len(ready))

    for item in ready[:10]:
        print(
            "-",
            item["analyst"],
            "|",
            item["analysis_score"],
            "|",
            item["title"],
        )


if __name__ == "__main__":
    main()
