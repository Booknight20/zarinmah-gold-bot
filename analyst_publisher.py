```python
import hashlib
import html
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit, urlunsplit

import requests


# =========================================================
# تنظیمات
# =========================================================

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

OUTPUT_FILE = "analyst_ready.json"
SEEN_FILE = "analyst_seen.json"
PUBLISHED_FILE = "analyst_published.json"

REQUEST_TIMEOUT = 30
MAX_POSTS_PER_SOURCE = 50

TELEGRAM_PUBLIC_URL = "https://t.me/s/"

ANALYSTS = [
    "Payamelyaskordi",
    "drarashamini",
    "nasiirry",
    "AlirezaMehrabi_ir",
    "rahavard365",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

MARKET_KEYWORDS = [
    "طلا", "طلای ۱۸", "طلای 18", "طلای ۱۸ عیار",
    "طلای آبشده", "آبشده", "آب‌شده", "مظنه",
    "سکه", "امامی", "نیم سکه", "نیم‌سکه",
    "ربع سکه", "ربع‌سکه", "گرمی", "پارسیان",
    "دلار", "تتر", "ارز", "یورو",
    "بورس", "شاخص کل", "شاخص هم وزن", "شاخص هم‌وزن",
    "سهام", "نماد", "عرضه اولیه", "فرابورس",
    "انس جهانی", "اونس جهانی", "انس طلا", "اونس طلا",
    "بازار سرمایه", "بازار ارز", "بازار طلا",
    "قیمت دلار", "قیمت طلا", "قیمت سکه",
]

ANALYSIS_KEYWORDS = [
    "تحلیل", "تحلیل تکنیکال", "تحلیل بنیادی",
    "پیش بینی", "پیش‌بینی", "پیشبینی",
    "سناریو", "هدف قیمتی", "تارگت",
    "حمایت", "مقاومت", "حد ضرر",
    "حد سود", "نقطه ورود", "نقطه خروج",
    "خرید", "فروش", "صعود", "نزول",
    "اصلاح", "روند", "موج", "شکست",
    "احتمال", "انتظار می رود", "انتظار می‌رود",
    "می تواند", "می‌تواند", "به نظر می رسد",
    "به نظر می‌رسد", "ریسک", "بازده",
    "ارزش ذاتی", "ارزش‌گذاری", "گزارش مالی",
    "صورت مالی", "حباب", "نرخ بهره",
    "نرخ ارز", "معاملات", "ورود پول",
    "خروج پول", "قدرت خریدار", "قدرت فروشنده",
    "حجم معاملات", "پیش بینی می شود",
    "پیش‌بینی می‌شود", "فردا", "هفته آینده",
    "ماه آینده", "کوتاه مدت", "کوتاه‌مدت",
    "میان مدت", "میان‌مدت", "بلند مدت", "بلندمدت",
]

PROMOTIONAL_KEYWORDS = [
    "تبلیغات", "تبلیغ", "اسپانسر",
    "ثبت نام کنید", "ثبت‌نام کنید",
    "عضویت ویژه", "اشتراک ویژه",
    "خرید اشتراک", "فروش دوره",
    "دوره آموزشی", "دوره VIP", "vip",
    "سیگنال VIP", "سیگنال vip",
    "سیگنال فروشی", "خرید سیگنال",
    "فروش سیگنال", "کانال پولی",
    "عضویت پولی", "کد تخفیف",
    "تخفیف ویژه", "ظرفیت محدود",
    "برای خرید پیام دهید", "جهت خرید پیام دهید",
    "مشاوره رایگان", "مشاوره تخصصی",
    "درآمد تضمینی", "سود تضمینی",
    "بدون ریسک", "سود قطعی",
]

PROMOTIONAL_LINK_PATTERNS = [
    r"t\.me/joinchat/",
    r"t\.me/\+",
    r"ثبت.?نام",
    r"خرید\s+(?:دوره|اشتراک|سیگنال)",
    r"عضویت\s+(?:ویژه|پولی)",
    r"دایرکت\s+بده",
    r"پیام\s+بده(?:ید)?\s+برای",
]

# این کلمات به‌تنهایی باعث حذف تحلیل نمی‌شوند؛
# فقط در کنار نشانه‌های تبلیغاتی بررسی می‌شوند.
PROMOTIONAL_CONTEXT_KEYWORDS = [
    "قیمت", "تحلیل", "طلا", "دلار", "سکه",
    "بورس", "سهام", "بازار", "سیگنال",
    "خرید", "فروش", "تارگت", "حمایت", "مقاومت",
]


# =========================================================
# ابزارهای عمومی
# =========================================================

def now_iso():
    return datetime.now(TEHRAN_TZ).isoformat()


def normalize_text(value):
    text = html.unescape(str(value or ""))
    text = text.replace("\u200c", " ")
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(value):
    text = normalize_text(value)
    return text.strip()


def atomic_save_json(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)

    fd, temporary_path = tempfile.mkstemp(
        prefix=".analyst_",
        suffix=".tmp",
        dir=directory,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_path, path)

    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def load_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    except Exception as error:
        raise RuntimeError(
            f"فایل {path} قابل خواندن نیست؛ "
            f"برای جلوگیری از ازدست‌رفتن وضعیت، اجرا متوقف شد: {error}"
        ) from error


def normalize_link(link):
    link = clean_text(link)

    if not link:
        return ""

    if link.startswith("t.me/"):
        link = "https://" + link

    if not link.startswith(("http://", "https://")):
        return link

    try:
        parts = urlsplit(link)
        host = parts.netloc.lower().removeprefix("www.")

        if host in ("t.me", "telegram.me"):
            path = re.sub(r"/+", "/", parts.path).rstrip("/")
            return urlunsplit(
                ("https", "t.me", path, "", "")
            )

        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                "",
                "",
            )
        )

    except Exception:
        return link


def post_id_from_link(link):
    link = normalize_link(link)

    match = re.search(
        r"https://t\.me/([A-Za-z0-9_]+)/([0-9]+)$",
        link,
    )

    if match:
        return f"{match.group(1)}/{match.group(2)}"

    return ""


def item_key(item):
    link = normalize_link(item.get("link"))

    if link:
        return link

    analyst = clean_text(
        item.get("analyst") or item.get("source")
    )
    title = clean_text(item.get("title"))
    collected_at = clean_text(item.get("collected_at"))

    raw = f"{analyst}|{title}|{collected_at}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    return f"fallback:{digest}"


# =========================================================
# خواندن و اعتبارسنجی فایل وضعیت
# =========================================================

def normalize_seen_data(data):
    if isinstance(data, list):
        return {
            str(value): True
            for value in data
            if value
        }

    if isinstance(data, dict):
        return data

    raise RuntimeError(
        f"{SEEN_FILE} باید فهرست یا شیء JSON باشد."
    )


def load_seen():
    data = load_json(SEEN_FILE, {})
    return normalize_seen_data(data)


def load_ready():
    data = load_json(OUTPUT_FILE, [])

    if not isinstance(data, list):
        raise RuntimeError(
            f"{OUTPUT_FILE} باید شامل فهرست JSON باشد."
        )

    return [
        item for item in data
        if isinstance(item, dict)
    ]


def published_items_map(data):
    """
    با ساختارهای قدیمی و جدید analyst_publisher.py سازگار است.
    """

    if isinstance(data, list):
        records = {}

        for record in data:
            if not isinstance(record, dict):
                continue

            item = record.get("item")

            if isinstance(item, dict):
                key = item_key(item)
            else:
                key = normalize_link(
                    record.get("link") or record.get("key")
                )

            if key:
                records[key] = record

        return records

    if not isinstance(data, dict):
        raise RuntimeError(
            f"{PUBLISHED_FILE} ساختار JSON نامعتبر دارد."
        )

    for container in ("items", "published", "posts", "analyses"):
        if isinstance(data.get(container), dict):
            return data[container]

    return data


def record_destination_sent(record, destination):
    if not isinstance(record, dict):
        return False

    parts = record.get(f"{destination}_parts_sent")

    if isinstance(parts, list) and parts:
        return all(bool(value) for value in parts)

    return bool(
        record.get(f"{destination}_sent")
        or record.get(f"{destination}_message_id")
        or record.get(f"{destination}_sent_at")
    )


def is_fully_published(record):
    return all(
        record_destination_sent(record, destination)
        for destination in ("telegram", "eitaa", "group")
    )


def load_published():
    data = load_json(PUBLISHED_FILE, {})
    return published_items_map(data)


# =========================================================
# دریافت پست‌های کانال عمومی تلگرام
# =========================================================

def fetch_channel(channel):
    url = f"{TELEGRAM_PUBLIC_URL}{channel}"

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    page = response.text

    if "tgme_widget_message" not in page:
        print(
            f"{channel}: نشانه‌ای از پست‌های عمومی "
            "در صفحه پیدا نشد."
        )

    blocks = re.findall(
        r'<div class="tgme_widget_message_wrap[^"]*"[^>]*>'
        r"(.*?)"
        r"(?=<div class=\"tgme_widget_message_wrap|"
        r"</section>|$)",
        page,
        flags=re.S,
    )

    results = []
    seen_links = set()

    for block in blocks:
        link_match = re.search(
            r'data-post="([^"]+)"',
            block,
        )

        if not link_match:
            link_match = re.search(
                r'href="(https?://t\.me/[^"]+)"[^>]*'
                r'class="tgme_widget_message_date"',
                block,
            )

        if not link_match:
            continue

        raw_link = html.unescape(link_match.group(1))

        if raw_link.startswith("http"):
            link = normalize_link(raw_link)
        else:
            link = normalize_link(
                "https://t.me/" + raw_link
            )

        if not link or link in seen_links:
            continue

        seen_links.add(link)

        text_match = re.search(
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>'
            r"(.*?)</div>",
            block,
            flags=re.S,
        )

        if not text_match:
            continue

        raw_text = text_match.group(1)

        raw_text = re.sub(
            r"<br\s*/?>",
            "\n",
            raw_text,
            flags=re.I,
        )

        raw_text = re.sub(
            r"</(?:div|p)>",
            "\n",
            raw_text,
            flags=re.I,
        )

        raw_text = re.sub(r"<[^>]+>", " ", raw_text)
        text = clean_text(raw_text)

        if not text:
            continue

        date_match = re.search(
            r'<time[^>]*datetime="([^"]+)"',
            block,
        )

        published_at = (
            date_match.group(1)
            if date_match
            else ""
        )

        results.append({
            "analyst": channel,
            "source": channel,
            "title": make_title(text),
            "full_text": text,
            "summary": text,
            "text": text,
            "content": text,
            "link": link,
            "source_published_at": published_at,
        })

    results.sort(
        key=lambda item: (
            post_id_from_link(item.get("link", "")) or ""
        )
    )

    return results[-MAX_POSTS_PER_SOURCE:]


# =========================================================
# تشخیص موضوع و تبلیغات
# =========================================================

def find_matches(text, keywords):
    normalized = normalize_text(text).lower()
    found = []

    for keyword in keywords:
        if keyword.lower() in normalized:
            found.append(keyword)

    return found


def make_title(text):
    text = clean_text(text)

    if not text:
        return "مرور دیدگاه جدید بازار"

    first_line = next(
        (
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ),
        text,
    )

    first_line = re.sub(r"\s+", " ", first_line)

    if len(first_line) > 110:
        first_line = first_line[:107].rstrip() + "..."

    return first_line


def is_promotional(text):
    normalized = normalize_text(text).lower()

    promo_matches = find_matches(
        normalized,
        PROMOTIONAL_KEYWORDS,
    )

    link_promo = any(
        re.search(pattern, normalized, flags=re.I)
        for pattern in PROMOTIONAL_LINK_PATTERNS
    )

    context_matches = find_matches(
        normalized,
        PROMOTIONAL_CONTEXT_KEYWORDS,
    )

    # تبلیغ صریح همراه با محتوای بازاری، احتمال تبلیغاتی بودن را بالا می‌برد.
    if link_promo and (
        promo_matches or context_matches
    ):
        return True

    if len(promo_matches) >= 2:
        return True

    # یک عبارت تبلیغاتی کوتاه به‌تنهایی برای حذف کافی نیست.
    if (
        len(normalized) < 350
        and promo_matches
        and not context_matches
    ):
        return True

    return False


def evaluate_analysis(text):
    normalized = normalize_text(text)

    market_matches = find_matches(
        normalized,
        MARKET_KEYWORDS,
    )
    analysis_matches = find_matches(
        normalized,
        ANALYSIS_KEYWORDS,
    )

    score = 0
    reasons = []

    if market_matches:
        score += min(len(market_matches), 5) * 2
        reasons.append(
            "اشاره به موضوعات بازار: "
            + "، ".join(market_matches[:8])
        )

    if analysis_matches:
        score += min(len(analysis_matches), 5) * 2
        reasons.append(
            "دارای نشانه‌های تحلیلی: "
            + "، ".join(analysis_matches[:8])
        )

    if len(normalized) >= 500:
        score += 2
        reasons.append("متن نسبتاً مفصل")

    if len(normalized) >= 1200:
        score += 2
        reasons.append("دارای جزئیات بیشتر")

    if re.search(r"\d", normalized):
        score += 1
        reasons.append("دارای عدد یا سطح قیمتی")

    # پست باید هم به بازار مرتبط باشد و هم نشانه‌ای از تحلیل داشته باشد.
    accepted = bool(
        market_matches
        and analysis_matches
        and score >= 6
    )

    if market_matches and not analysis_matches:
        reasons.append("فاقد نشانه کافی از تحلیل")

    if analysis_matches and not market_matches:
        reasons.append("موضوع بازار هدف به‌روشنی مشخص نیست")

    return {
        "accepted": accepted,
        "score": score,
        "market_matches": market_matches,
        "analysis_matches": analysis_matches,
        "reasons": reasons,
    }


def make_item(raw):
    text = clean_text(
        raw.get("full_text")
        or raw.get("text")
        or raw.get("content")
        or raw.get("summary")
    )

    evaluation = evaluate_analysis(text)

    channel = clean_text(
        raw.get("analyst") or raw.get("source")
    )

    link = normalize_link(raw.get("link"))

    title = clean_text(raw.get("title")) or make_title(text)

    priority = (
        "high"
        if evaluation["score"] >= 14
        else "medium"
    )

    return {
        "analyst": channel,
        "title": title,
        "summary": text,
        "full_text": text,
        "source": channel,
        "link": link,
        "analysis_score": evaluation["score"],
        "market_matches": evaluation["market_matches"],
        "analysis_matches": evaluation["analysis_matches"],
        "market_groups": evaluation["market_matches"],
        "analysis_reasons": evaluation["reasons"],
        "priority": priority,
        "content_length": len(text),
        "content_complete_from_source": True,
        "source_published_at": raw.get("source_published_at", ""),
        "collected_at": now_iso(),
    }


# =========================================================
# مدیریت صف و جلوگیری از تکرار
# =========================================================

def merge_items(*item_groups):
    merged = {}
    order = []

    for group in item_groups:
        for item in group:
            if not isinstance(item, dict):
                continue

            key = item_key(item)

            if key not in merged:
                merged[key] = item
                order.append(key)
                continue

            # در صورت تکرار، متن کامل‌تر را نگه می‌داریم.
            old_item = merged[key]
            old_text = clean_text(old_item.get("full_text"))
            new_text = clean_text(item.get("full_text"))

            if len(new_text) > len(old_text):
                merged[key] = item

    return [merged[key] for key in order]


def get_pending_published_items(published):
    pending = []

    for record in published.values():
        if not isinstance(record, dict):
            continue

        item = record.get("item")

        if not isinstance(item, dict):
            continue

        if not is_fully_published(record):
            pending.append(item)

    return pending


def remove_fully_published_from_ready(items, published):
    result = []

    for item in items:
        key = item_key(item)
        record = published.get(key)

        if isinstance(record, dict) and is_fully_published(record):
            continue

        result.append(item)

    return result


# =========================================================
# اجرای اصلی
# =========================================================

def main():
    print("===================================")
    print("ZarinMah Analyst Collector")
    print("===================================")

    # اگر هر فایل وضعیت خراب باشد، load_json اجرا را متوقف می‌کند.
    seen = load_seen()
    ready_before = load_ready()
    published = load_published()

    # صف موجود و تحلیل‌های منتشرنشده حفظ می‌شوند.
    pending_items = get_pending_published_items(published)

    collected_items = []
    newly_seen = {}
    errors = []

    for channel in ANALYSTS:
        print(f"\nChecking source: {channel}")

        try:
            posts = fetch_channel(channel)
            print(f"{channel}: {len(posts)} posts fetched.")

        except Exception as error:
            errors.append(f"{channel}: {error}")
            print(f"{channel}: FETCH FAILED: {error}")
            continue

        for raw in posts:
            link = normalize_link(raw.get("link"))
            key = link or item_key(raw)

            # پست‌های دیده‌شده را دوباره وارد صف نکن.
            if key in seen:
                continue

            text = clean_text(raw.get("full_text"))

            if not text:
                continue

            # پست تبلیغاتی را در صف تحلیل قرار نده.
            if is_promotional(text):
                newly_seen[key] = {
                    "status": "rejected_promotional",
                    "analyst": channel,
                    "link": link,
                    "seen_at": now_iso(),
                }
                continue

            item = make_item(raw)

            evaluation = evaluate_analysis(text)

            if not evaluation["accepted"]:
                # ردشده‌ها نیز ثبت می‌شوند تا در هر اجرا دوباره بررسی نشوند.
                newly_seen[key] = {
                    "status": "rejected_low_relevance",
                    "analyst": channel,
                    "link": link,
                    "analysis_score": evaluation["score"],
                    "seen_at": now_iso(),
                }
                continue

            collected_items.append(item)

            newly_seen[key] = {
                "status": "accepted",
                "analyst": channel,
                "link": link,
                "seen_at": now_iso(),
            }

            print(
                "Accepted:",
                channel,
                "|",
                item.get("title", ""),
                "| score:",
                item.get("analysis_score", 0),
            )

    # صف قبلی، تحلیل‌های جدید و موارد ناقص انتشار را ادغام می‌کنیم.
    combined = merge_items(
        ready_before,
        pending_items,
        collected_items,
    )

    combined = remove_fully_published_from_ready(
        combined,
        published,
    )

    # ابتدا صف را ذخیره می‌کنیم؛ سپس seen را ثبت می‌کنیم.
    # اگر ذخیره صف شکست بخورد، پست‌های جدید به‌عنوان دیده‌شده ثبت نمی‌شوند.
    atomic_save_json(OUTPUT_FILE, combined)

    seen.update(newly_seen)
    atomic_save_json(SEEN_FILE, seen)

    print("\n===================================")
    print(f"صف نهایی تحلیل‌ها: {len(combined)}")
    print(f"پست‌های جدید پذیرفته‌شده: {len(collected_items)}")
    print(f"موارد ثبت‌شده در وضعیت دیده‌شده: {len(newly_seen)}")
    print("===================================")

    if errors:
        print("\nبرخی منابع با خطا مواجه شدند:")

        for error in errors:
            print("-", error)

        # شکست یک منبع را پنهان نمی‌کنیم تا اجرای بعدی مجدداً تلاش کند.
        sys.exit(1)

    print("Analyst collection completed successfully.")


if __name__ == "__main__":
    main()
```
