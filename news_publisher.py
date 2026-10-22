import hashlib
import html
import json
import os
import re
from datetime import datetime

import requests


# =========================================================
# تنظیمات
# =========================================================

INPUT_FILE = "news_ready.json"
PUBLISHED_FILE = "news_published.json"

CHANNEL = "@ZarinMahGold"

NEWS_GROUP = "@ZarinMahCommunity"
NEWS_THREAD_ID = 15

TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN"
)

EITAAYAR_TOKEN = os.environ.get(
    "EITAAYAR_TOKEN"
)

EITAA_CHAT_ID = os.environ.get(
    "EITAA_CHAT_ID"
)

EITAA_API_URL = "https://eitaayar.ir/api"

# برای جلوگیری از عبور از محدودیت طول پیام،
# هر بخش با فاصله کافی از سقف تلگرام ساخته می‌شود.
MAX_PART_CHARS = 3200

REQUEST_TIMEOUT = 30


# =========================================================
# ابزار تاریخ و JSON
# =========================================================

def now_iso():
    return datetime.now().astimezone().isoformat()


def parse_datetime(value):
    if not value:
        return None

    try:
        result = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if result.tzinfo is None:
            result = result.astimezone()

        return result

    except (ValueError, TypeError, OverflowError):
        return None


def comparable_datetime(value):
    parsed = parse_datetime(value)

    if parsed is None:
        return None

    return parsed.timestamp()


def load_json_file(filename, default):
    if not os.path.exists(filename):
        return default

    try:
        with open(
            filename,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except Exception as error:
        print(f"Could not load {filename}: {error}")
        return default


def save_json_file(filename, data):
    temporary_file = filename + ".tmp"

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

    os.replace(temporary_file, filename)


# =========================================================
# شناسه خبر
# =========================================================

def normalize_url(url):
    url = str(url or "").strip()

    if not url:
        return ""

    # حذف پارامترهای رایج رهگیری
    url = re.sub(
        r"([?&])utm_[^&]*",
        "",
        url,
        flags=re.IGNORECASE,
    )

    url = re.sub(
        r"([?&])(fbclid|gclid|ref|campaign)=[^&]*",
        "",
        url,
        flags=re.IGNORECASE,
    )

    url = url.rstrip("?&")

    return url.rstrip("/")


def create_news_id(item):
    link = normalize_url(item.get("link", ""))
    title = normalize_text(item.get("title", ""))

    base = link or title

    return hashlib.sha256(
        base.encode("utf-8")
    ).hexdigest()


def normalize_text(text):
    text = str(text or "")

    text = text.replace("ي", "ی")
    text = text.replace("ى", "ی")
    text = text.replace("ك", "ک")
    text = text.replace("ۀ", "ه")
    text = text.replace("ة", "ه")
    text = text.replace("\u200c", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


# =========================================================
# بررسی ارزش انتشار
# =========================================================

PROMOTIONAL_PATTERNS = [
    r"عضویت در کانال",
    r"تبلیغات پذیرفته می‌شود",
    r"تبلیغات پذیرفته میشود",
    r"جهت تبلیغات",
    r"برای تبلیغات تماس",
    r"ثبت سفارش",
    r"خرید دوره",
    r"فروش دوره",
    r"سیگنال تضمینی",
    r"سود تضمینی",
    r"درآمد تضمینی",
    r"فرصت استثنایی خرید",
    r"همین حالا بخرید",
    r"تخفیف ویژه",
    r"کد تخفیف",
    r"لینک عضویت",
]


MARKET_FIELDS = (
    "gold_matches",
    "currency_matches",
    "stock_matches",
    "market_matches",
    "title_market_matches",
    "summary_market_matches",
)


def has_market_evidence(item):
    for field in MARKET_FIELDS:
        value = item.get(field)

        if isinstance(value, dict) and value:
            return True

        if isinstance(value, (list, tuple, set)) and value:
            return True

    # پشتیبانی از داده‌های قدیمی که فقط امتیاز دارند.
    title = normalize_text(item.get("title", ""))
    summary = normalize_text(item.get("summary", ""))
    text = f"{title} {summary}"

    market_terms = [
        "طلا",
        "آبشده",
        "سکه",
        "دلار",
        "ارز",
        "بورس",
        "بازار سرمایه",
        "شاخص کل",
        "اونس جهانی",
        "طلای ۱۸ عیار",
        "طلای 18 عیار",
        "نرخ ارز",
    ]

    return any(term in text for term in market_terms)


def is_promotional(item):
    title = normalize_text(item.get("title", ""))
    summary = normalize_text(item.get("summary", ""))

    # عنوان به‌تنهایی برای رد خبر کافی نیست؛
    # تبلیغ باید با چند نشانه مشخص همراه باشد.
    text = f"{title} {summary}"

    matched = [
        pattern
        for pattern in PROMOTIONAL_PATTERNS
        if re.search(pattern, text)
    ]

    commercial_terms = [
        "خرید دوره",
        "فروش دوره",
        "ثبت سفارش",
        "کد تخفیف",
        "سود تضمینی",
        "سیگنال تضمینی",
        "درآمد تضمینی",
    ]

    if any(term in text for term in commercial_terms):
        return True

    if len(matched) >= 2:
        return True

    return False


def get_market_score(item):
    try:
        return float(item.get("market_score", 0))
    except (TypeError, ValueError):
        return 0.0


def is_publishable(item):
    """
    تعداد خبرها محدود نیست.
    فقط خبرهای دارای ارتباط روشن با بازار،
    امتیاز کافی و اولویت مناسب منتشر می‌شوند.
    """

    priority = str(
        item.get("priority", "")
    ).strip().lower()

    if priority not in ("high", "medium"):
        return False

    if not has_market_evidence(item):
        return False

    minimum_score = 9 if priority == "medium" else 18

    if get_market_score(item) < minimum_score:
        return False

    if is_promotional(item):
        return False

    if not str(item.get("title", "")).strip():
        return False

    if not str(item.get("link", "")).strip():
        return False

    return True


# =========================================================
# آماده‌سازی متن
# =========================================================

def clean_text(text):
    text = str(text or "")

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = text.replace("\u200c", "‌")
    text = text.replace("\u200f", "")
    text = text.replace("\ufeff", "")

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def build_plain_message(item):
    title = clean_text(item.get("title", ""))
    summary = clean_text(item.get("summary", ""))
    source = clean_text(item.get("source", ""))
    link = str(item.get("link", "") or "").strip()

    parts = [
        "🌙 زرین ماه",
        "",
        f"📰 {title}",
    ]

    if summary:
        parts.extend(["", summary])

    if source:
        parts.extend(["", f"📌 منبع: {source}"])

    if link:
        parts.extend(["", f"🔗 مشاهده خبر کامل: {link}"])

    parts.extend([
        "",
        "🌙 اخبار و تحلیل‌های بیشتر زرین ماه",
        "https://t.me/ZarinMahGold",
        "",
        "#اخبار_بازار",
    ])

    return "\n".join(parts)


def split_message(text, max_chars=MAX_PART_CHARS):
    """
    متن را ترجیحاً در مرز پاراگراف و جمله تقسیم می‌کند.
    هیچ متن طولانی‌ای به‌صورت بی‌صدا حذف نمی‌شود.
    """

    text = str(text or "").strip()

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n")
    chunks = []
    current = ""

    def flush():
        nonlocal current

        if current.strip():
            chunks.append(current.strip())

        current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()

        if not paragraph:
            candidate = current + "\n"

            if len(candidate) <= max_chars:
                current = candidate

            continue

        while len(paragraph) > max_chars:
            if current:
                flush()

            # شکستن پاراگراف خیلی طولانی در نزدیک‌ترین فاصله
            cut = paragraph.rfind(" ", 0, max_chars + 1)

            if cut < max_chars // 2:
                cut = max_chars

            chunks.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()

        candidate = (
            current + "\n" + paragraph
            if current else paragraph
        )

        if len(candidate) <= max_chars:
            current = candidate
        else:
            flush()
            current = paragraph

    flush()

    return [chunk for chunk in chunks if chunk]


def build_parts(item):
    base_message = build_plain_message(item)
    chunks = split_message(base_message)

    if len(chunks) <= 1:
        return chunks

    total = len(chunks)

    return [
        f"📄 بخش {index} از {total}\n\n{chunk}"
        for index, chunk in enumerate(chunks, start=1)
    ]


def build_telegram_html_message(plain_text):
    """
    متن را به‌صورت HTML امن برای تلگرام می‌فرستد.
    """
    return html.escape(plain_text)


# =========================================================
# ارسال به تلگرام
# =========================================================

def send_to_telegram(
    message,
    chat_id=CHANNEL,
    message_thread_id=None,
):
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

    url = (
        "https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": build_telegram_html_message(message),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if message_thread_id is not None:
        payload["message_thread_id"] = message_thread_id

    response = requests.post(
        url,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    print(
        "Telegram destination:",
        chat_id,
        "topic:",
        message_thread_id if message_thread_id is not None else "default",
        "HTTP:",
        response.status_code,
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API returned ok=false: {result}"
        )

    message_id = (
        result.get("result", {}).get("message_id")
    )

    if message_id is None:
        raise RuntimeError(
            "Telegram response has no message_id."
        )

    return message_id


# =========================================================
# ارسال به ایتا
# =========================================================

def send_to_eitaa(message):
    if not EITAAYAR_TOKEN:
        raise RuntimeError("EITAAYAR_TOKEN is missing.")

    if not EITAA_CHAT_ID:
        raise RuntimeError("EITAA_CHAT_ID is missing.")

    token = EITAAYAR_TOKEN.strip()
    chat_id = EITAA_CHAT_ID.strip().lstrip("@")

    url = f"{EITAA_API_URL}/{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
    }

    response = requests.post(
        url,
        data=payload,
        timeout=REQUEST_TIMEOUT,
    )

    print(
        "Eitaa HTTP status:",
        response.status_code,
    )

    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as error:
        raise RuntimeError(
            "Eitaa API returned invalid JSON."
        ) from error

    if not result.get("ok"):
        raise RuntimeError(
            f"Eitaa API returned ok=false: {result}"
        )

    message_id = (
        result.get("result", {}).get("message_id")
    )

    if message_id is None:
        message_id = (
            result.get("result", {}).get("id")
        )

    # اگر API موفقیت را اعلام کرده اما شناسه پیام نداده،
    # وضعیت موفقیت را با نشانگر ثبت می‌کنیم تا تکرار ناخواسته نشود.
    return message_id if message_id is not None else "sent"


# =========================================================
# وضعیت انتشار و سازگاری با فایل قبلی
# =========================================================

def initialize_publisher(published):
    meta = published.get("__meta__")

    if isinstance(meta, dict):
        initialized_at = parse_datetime(
            meta.get("initialized_at")
        )

        if initialized_at:
            return initialized_at, False

    initialized_at = datetime.now().astimezone()

    published["__meta__"] = {
        "initialized_at": initialized_at.isoformat()
    }

    save_json_file(PUBLISHED_FILE, published)

    return initialized_at, True


def get_collected_datetime(item):
    return parse_datetime(item.get("collected_at", ""))


def get_sort_value(item):
    return (
        item.get("published")
        or item.get("collected_at")
        or ""
    )


def ensure_record(published, news_id, item):
    record = published.get(news_id, {})

    if not isinstance(record, dict):
        record = {}

    record.setdefault("title", item.get("title", ""))
    record.setdefault("source", item.get("source", ""))
    record.setdefault("link", item.get("link", ""))
    record.setdefault("published_at", now_iso())

    # تبدیل شناسه‌های قدیمی به فهرست بخش‌ها
    for destination in (
        "telegram",
        "eitaa",
        "group",
    ):
        list_key = f"{destination}_message_ids"

        if list_key not in record:
            legacy_key = f"{destination}_message_id"
            legacy_value = record.get(legacy_key)

            record[list_key] = (
                [legacy_value]
                if legacy_value is not None
                else []
            )

    published[news_id] = record

    return record


def save_record(published, news_id, record):
    published[news_id] = record
    save_json_file(PUBLISHED_FILE, published)


def send_parts_to_destination(
    *,
    parts,
    record,
    published,
    news_id,
    destination,
    chat_id=None,
    thread_id=None,
):
    ids_key = f"{destination}_message_ids"
    sent_ids = record.setdefault(ids_key, [])

    # وضعیت قدیمی ممکن است یک پیام ثبت کرده باشد.
    if not isinstance(sent_ids, list):
        sent_ids = []
        record[ids_key] = sent_ids

    while len(sent_ids) < len(parts):
        sent_ids.append(None)

    for index, part in enumerate(parts):
        if sent_ids[index] is not None:
            continue

        print(
            f"Sending {destination}: "
            f"part {index + 1}/{len(parts)}"
        )

        if destination == "telegram":
            message_id = send_to_telegram(
                part,
                chat_id=chat_id or CHANNEL,
            )
        elif destination == "group":
            message_id = send_to_telegram(
                part,
                chat_id=chat_id or NEWS_GROUP,
                message_thread_id=thread_id or NEWS_THREAD_ID,
            )
        elif destination == "eitaa":
            message_id = send_to_eitaa(part)
        else:
            raise ValueError(
                f"Unknown destination: {destination}"
            )

        sent_ids[index] = message_id

        # برای هر بخش بلافاصله وضعیت ذخیره می‌شود.
        record[ids_key] = sent_ids
        record[f"{destination}_last_sent_at"] = now_iso()

        # حفظ کلیدهای قدیمی برای سازگاری با سابقه انتشار
        if index == 0:
            record[f"{destination}_message_id"] = message_id

        save_record(
            published,
            news_id,
            record,
        )

    return True


def is_fully_published(record, expected_parts):
    for destination in ("telegram", "eitaa", "group"):
        ids = record.get(
            f"{destination}_message_ids",
            [],
        )

        if not isinstance(ids, list):
            return False

        if len(ids) < expected_parts:
            return False

        if any(value is None for value in ids[:expected_parts]):
            return False

    return True


# =========================================================
# اجرای اصلی
# =========================================================

def main():
    print("===================================")
    print("ZarinMah News Publisher")
    print("===================================")

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

    if not EITAAYAR_TOKEN:
        raise RuntimeError("EITAAYAR_TOKEN is missing.")

    if not EITAA_CHAT_ID:
        raise RuntimeError("EITAA_CHAT_ID is missing.")

    news = load_json_file(INPUT_FILE, [])

    if not isinstance(news, list):
        raise RuntimeError(
            f"{INPUT_FILE} must contain a JSON list."
        )

    published = load_json_file(PUBLISHED_FILE, {})

    if not isinstance(published, dict):
        published = {}

    initialized_at, is_first_run = initialize_publisher(
        published
    )

    if is_first_run:
        print("Publisher initialized.")
        print("Old news will not be published on the first run.")
        return

    print(
        "Publisher initialized at:",
        initialized_at.isoformat(),
    )

    # هیچ سقف تعدادی برای خبرهای واجد شرایط وجود ندارد.
    eligible_news = [
        item
        for item in news
        if is_publishable(item)
    ]

    eligible_news.sort(
        key=get_sort_value,
        reverse=True,
    )

    print("Total ready news:", len(news))
    print("Eligible news:", len(eligible_news))

    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for item in eligible_news:
        news_id = create_news_id(item)

        record = ensure_record(
            published,
            news_id,
            item,
        )

        collected_at = get_collected_datetime(item)

        if collected_at is None:
            print(
                "Skipping news with invalid collection time:",
                item.get("title", ""),
            )
            skipped_count += 1
            continue

        # جلوگیری از انتشار آرشیو موجود قبل از شروع ناشر
        if collected_at.timestamp() <= initialized_at.timestamp():
            # اگر قبلاً بخشی از این خبر ارسال شده،
            # اجازه می‌دهیم ادامه انتشار ناقص تکمیل شود.
            has_previous_delivery = any(
                record.get(f"{destination}_message_ids")
                for destination in ("telegram", "eitaa", "group")
            )

            if not has_previous_delivery:
                skipped_count += 1
                continue

        parts = build_parts(item)

        if not parts:
            skipped_count += 1
            continue

        if is_fully_published(record, len(parts)):
            skipped_count += 1
            continue

        print()
        print("Publishing:", item.get("title", ""))
        print("Priority:", item.get("priority"))
        print("Market score:", item.get("market_score"))
        print("Message parts:", len(parts))

        try:
            send_parts_to_destination(
                parts=parts,
                record=record,
                published=published,
                news_id=news_id,
                destination="telegram",
                chat_id=CHANNEL,
            )

            send_parts_to_destination(
                parts=parts,
                record=record,
                published=published,
                news_id=news_id,
                destination="eitaa",
            )

            send_parts_to_destination(
                parts=parts,
                record=record,
                published=published,
                news_id=news_id,
                destination="group",
                chat_id=NEWS_GROUP,
                thread_id=NEWS_THREAD_ID,
            )

            record["expected_parts"] = len(parts)
            record["fully_published"] = is_fully_published(
                record,
                len(parts),
            )

            save_record(
                published,
                news_id,
                record,
            )

            if record["fully_published"]:
                sent_count += 1
                print("Publication completed in all destinations.")
            else:
                failed_count += 1
                print("Publication remains incomplete.")

        except Exception as error:
            failed_count += 1

            print(
                "Publishing failed:",
                item.get("title", ""),
                error,
            )

            # وضعیت مقصدهایی که موفق بوده‌اند حفظ می‌شود؛
            # اجرای بعدی فقط بخش‌های ثبت‌نشده را تلاش می‌کند.
            save_record(
                published,
                news_id,
                record,
            )

    print()
    print("===================================")
    print("Publishing finished")
    print("===================================")
    print("Published this run:", sent_count)
    print("Skipped:", skipped_count)
    print("Failed or incomplete:", failed_count)

    if failed_count:
        raise RuntimeError(
            f"{failed_count} publication(s) failed or remain incomplete."
        )


if __name__ == "__main__":
    main()
