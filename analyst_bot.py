
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
PUBLISHED_FILE = "analyst_published.json"

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
# زمان و نرمال‌سازی
# =========================================================

def now_iso():
    return datetime.now(TEHRAN_TZ).isoformat()


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
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)

    text = text.replace("\u200f", "")
    text = text.replace("\u200e", "")
    text = text.replace("\ufeff", "")
    text = text.replace("\u00a0", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n{2,}", "\n\n", text)

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


def compact_telegram_link(link):
    link = str(link or "").strip()

    match = re.search(
        r"(?:https?://)?(?:www\.)?t\.me/([A-Za-z0-9_]+)/([0-9]+)",
        link,
    )

    if match:
        return f"https://t.me/{match.group(1)}/{match.group(2)}"

    return link


def item_key(item):
    link = compact_telegram_link(item.get("link"))

    if link:
        return link

    analyst = str(
        item.get("analyst") or item.get("source") or "تحلیلگر"
    ).strip()

    title = str(item.get("title", "")).strip()
    collected_at = str(item.get("collected_at", "")).strip()

    return f"{analyst}|{title}|{collected_at}"


# =========================================================
# ذخیره امن فایل‌ها
# =========================================================

def load_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    except Exception as error:
        print(f"Could not load {path}: {error}")
        return default


def save_json(path, data):
    temporary_file = path + ".tmp"

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(temporary_file, path)


def load_seen():
    data = load_json(SEEN_FILE, {"sources": {}})

    if not isinstance(data, dict):
        data = {"sources": {}}

    if not isinstance(data.get("sources"), dict):
        data["sources"] = {}

    return data


# =========================================================
# خواندن وضعیت انتشار
# =========================================================

def get_published_records():
    data = load_json(PUBLISHED_FILE, {})

    if isinstance(data, list):
        mapped = {}

        for record in data:
            if isinstance(record, dict):
                key = record.get("link") or record.get("key")
                if key:
                    mapped[str(key)] = record

        return mapped

    if not isinstance(data, dict):
        return {}

    for container_name in ("items", "published", "posts", "analyses"):
        container = data.get(container_name)

        if isinstance(container, dict):
            return container

    return data


def destination_is_sent(record, destination):
    if not isinstance(record, dict):
        return False

    parts = record.get(f"{destination}_parts_sent")

    if isinstance(parts, list) and parts:
        return all(parts)

    return bool(
        record.get(f"{destination}_sent")
        or record.get(f"{destination}_message_id")
        or record.get(f"{destination}_sent_at")
    )


def is_fully_published(record):
    return all(
        destination_is_sent(record, destination)
        for destination in ("telegram", "eitaa", "group")
    )


def get_pending_items(published_records):
    pending = {}

    for key, record in published_records.items():
        if not isinstance(record, dict):
            continue

        item = record.get("item")

        if not isinstance(item, dict):
            continue

        if is_fully_published(record):
            continue

        pending[item_key(item)] = item

    return pending


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
        text = clean_html(match.group(2))

        if not link or not text:
            continue

        posts.append({
            "link": compact_telegram_link(link),
            "text": text,
        })

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

    strong_promotions = {
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

    if any(normalize(value) in strong_promotions for value in promo_matches):
        if len(analysis_matches) < 3:
            return True

    if (
        len(promo_matches) >= 2
        and len(cta_matches) >= 1
        and len(analysis_matches) < 3
        and len(market_matches) < 5
    ):
        return True

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
    return bool(
        re.search(r"\d+(?:[.,]\d+)?\s*%?", normalize(text))
    )


def has_reasoning_structure(text):
    normalized_text = normalize(text)

    reasoning_patterns = [
        "به دلیل", "زیرا", "در نتیجه", "بنابراین",
        "اگر", "در صورتی که", "از طرفی",
        "با توجه به", "عامل اصلی", "علت این",
        "ناشی از", "در مقابل", "اما اگر",
        "مشروط به", "به شرط",
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

    score += min(len(market_matches), 8) * 2

    if market_matches:
        reasons.append("ارتباط با بازار")

    score += min(len(analysis_matches), 6) * 2

    if analysis_matches:
        reasons.append("دارای نشانه‌های تحلیل")

    if len(text) >= 250:
        score += 1
        reasons.append("دارای توضیح")

    if len(text) >= 700:
        score += 1

    if has_numeric_evidence(text):
        score += 2
        reasons.append("دارای داده عددی")

    if has_reasoning_structure(text):
        score += 3
        reasons.append("دارای استدلال")

    market_groups = {
        "gold": ["طلا", "آبشده", "اونس", "سکه"],
        "currency": ["دلار", "ارز", "یورو", "درهم", "تتر"],
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

    has_analysis = bool(analysis_matches)
    has_reasoning = has_reasoning_structure(text)
    sufficient_length = len(text) >= 180

    relevant = (
        (score >= 8 and has_analysis)
        or (
            score >= 7
            and has_reasoning
            and sufficient_length
        )
        or (
            len(market_matches) >= 2
            and has_analysis
            and len(text) >= 120
        )
    )

    return {
        "relevant": relevant,
        "score": score,
        "market_matches": market_matches,
        "analysis_matches": analysis_matches,
        "market_groups": matched_groups,
        "reasons": reasons,
        "reject_reason": (
            "" if relevant else "insufficient_analysis_evidence"
        ),
    }


def is_relevant(text):
    result = evaluate_analysis(text)

    return (
        result["relevant"],
        result["score"],
        result["market_matches"],
    )


# =========================================================
# ساخت آیتم تحلیل
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
    # متن کامل در دسترس از پست عمومی حفظ می‌شود.
    return clean_html(text)


def make_item(source_name, post, evaluation):
    full_text = clean_html(post.get("text", ""))
    score = evaluation["score"]

    return {
        "analyst": source_name,
        "title": build_title(full_text),
        "summary": build_summary(full_text),
        "full_text": full_text,
        "source": source_name,
        "link": compact_telegram_link(post["link"]),
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
    sources = seen.setdefault("sources", {})

    if source_name in sources:
        return False

    post_ids = [
        compact_telegram_link(post["link"])
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
    print("Existing posts registered:", len(post_ids))

    return True


def source_has_post(seen, source_name, post_id):
    sources = seen.setdefault("sources", {})
    source_data = sources.get(source_name, {})

    if not isinstance(source_data, dict):
        return False

    return compact_telegram_link(post_id) in source_data.get(
        "post_ids", []
    )


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
    normalized_id = compact_telegram_link(post_id)

    if normalized_id not in post_ids:
        post_ids.append(normalized_id)

    source_data["post_ids"] = list(
        dict.fromkeys(post_ids)
    )[-MAX_SEEN_POSTS_PER_SOURCE:]


# =========================================================
# ادغام صف جدید با تحلیل‌های در انتظار
# =========================================================

def merge_pending_and_new(pending, previous_ready, new_items, published):
    """
    صف نهایی شامل موارد زیر است:
    1. تحلیل‌های ناقص ثبت‌شده در فایل وضعیت انتشار
    2. موارد قبلی آماده انتشار که هنوز کامل منتشر نشده‌اند
    3. تحلیل‌های جدید پذیرفته‌شده

    موارد کاملاً منتشرشده به صف بازگردانده نمی‌شوند.
    """

    merged = {}

    def add_if_pending(item):
        if not isinstance(item, dict):
            return

        key = item_key(item)
        record = published.get(key)

        # برای رکوردهایی که کلیدشان در قالب قدیمی متفاوت بوده،
        # لینک هم بررسی می‌شود.
        if record is None:
            link = compact_telegram_link(item.get("link"))
            for old_key, old_record in published.items():
                if not isinstance(old_record, dict):
                    continue

                old_item = old_record.get("item")
                if not isinstance(old_item, dict):
                    continue

                if compact_telegram_link(old_item.get("link")) == link and link:
                    record = old_record
                    break

        if isinstance(record, dict) and is_fully_published(record):
            return

        merged[key] = item

    for item in pending.values():
        add_if_pending(item)

    for item in previous_ready:
        add_if_pending(item)

    for item in new_items:
        add_if_pending(item)

    return sorted(
        merged.values(),
        key=lambda item: item.get("analysis_score", 0),
        reverse=True,
    )


# =========================================================
# اجرای اصلی
# =========================================================

def main():
    print("===================================")
    print("ZarinMah Analyst Collector")
    print("===================================")

    seen = load_seen()

    published_records = get_published_records()
    pending_items = get_pending_items(published_records)

    # صف قبلی را قبل از جایگزین کردن خروجی فعلی می‌خوانیم.
    previous_ready = load_json(OUTPUT_FILE, [])

    if not isinstance(previous_ready, list):
        previous_ready = []

    new_items = []

    for source_name, config in ANALYSTS.items():
        print("\nReading:", source_name)

        try:
            posts = fetch_channel(config["channel"])

        except Exception as error:
            print("Channel error:", source_name, error)
            continue

        print("Posts found:", len(posts))

        # اولین اجرا، پست‌های آرشیوی را ثبت می‌کند اما منتشر نمی‌کند.
        if initialize_source(seen, source_name, posts):
            continue

        for post in posts:
            post_id = compact_telegram_link(post.get("link"))

            if not post_id:
                continue

            if source_has_post(seen, source_name, post_id):
                continue

            text = clean_html(post.get("text", ""))

            if not text:
                mark_source_post(seen, source_name, post_id)
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

                # پست ردشده فعلاً دیده‌شده محسوب نمی‌شود؛
                # در اجرای بعدی دوباره ارزیابی خواهد شد.
                continue

            item = make_item(source_name, post, evaluation)
            new_items.append(item)

            mark_source_post(seen, source_name, post_id)

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

    # ابتدا صف نهایی را ذخیره می‌کنیم، سپس وضعیت پست‌های دیده‌شده را.
    # اگر اجرای برنامه بین این دو مرحله قطع شود، پست جدید در صف می‌ماند.
    ready = merge_pending_and_new(
        pending=pending_items,
        previous_ready=previous_ready,
        new_items=new_items,
        published=published_records,
    )

    save_json(OUTPUT_FILE, ready)
    save_json(SEEN_FILE, seen)

    print("\nNew accepted analyses:", len(new_items))
    print("Pending analyses recovered:", len(pending_items))
    print("Total items in ready queue:", len(ready))

    for item in ready[:10]:
        print(
            "-",
            item.get("analyst", "تحلیلگر"),
            "|",
            item.get("analysis_score", 0),
            "|",
            item.get("title", ""),
        )


if __name__ == "__main__":
    main()
