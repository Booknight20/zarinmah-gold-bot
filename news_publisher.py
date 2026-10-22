import hashlib
import html
import json
import os
import re
import tempfile
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

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
EITAAYAR_TOKEN = os.environ.get("EITAAYAR_TOKEN")
EITAA_CHAT_ID = os.environ.get("EITAA_CHAT_ID")

EITAA_API_URL = "https://eitaayar.ir/api"

# تقسیم محافظه‌کارانه برای سازگاری بهتر با مقصدها
MAX_PART_CHARS = 2300
REQUEST_TIMEOUT = 30


# =========================================================
# تاریخ
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


def get_collected_datetime(item):
    # زمان جمع‌آوری اولویت دارد.
    # در نبود آن، تاریخ انتشار را بررسی می‌کنیم.
    return (
        parse_datetime(item.get("collected_at"))
        or parse_datetime(item.get("published"))
    )


# =========================================================
# خواندن و ذخیره امن JSON
# =========================================================

def load_json_file(filename, default, required=False):
    if not os.path.exists(filename):
        if required:
            raise FileNotFoundError(
                f"فایل ضروری پیدا نشد: {filename}"
            )

        return default

    try:
        with open(
            filename,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except Exception as error:
        raise RuntimeError(
            f"خواندن {filename} ناموفق بود: {error}"
        ) from error


def save_json_file(filename, data):
    output_dir = os.path.dirname(
        os.path.abspath(filename)
    )

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_dir,
            prefix=".publisher_",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = file.name

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

            file.write("\n")

        os.replace(
            temporary_path,
            filename,
        )

    except Exception:
        if temporary_path and os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                pass

        raise


# =========================================================
# پاک‌سازی و نرمال‌سازی
# =========================================================

def clean_text(value):
    if value is None:
        return ""

    text = str(value)

    text = re.sub(
        r"(?i)<br\s*/?>",
        "\n",
        text,
    )

    text = re.sub(
        r"(?i)</(?:p|div|li|h[1-6])\s*>",
        "\n",
        text,
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
    text = text.replace("\u200c", "‌")

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r" *\n *",
        "\n",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def normalize_text(value):
    text = clean_text(value)

    text = text.replace("ي", "ی")
    text = text.replace("ى", "ی")
    text = text.replace("ك", "ک")
    text = text.replace("ۀ", "ه")
    text = text.replace("ة", "ه")

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip().lower()


def normalize_url(url):
    url = str(url or "").strip()

    if not url:
        return ""

    # حذف پارامترهای رهگیری
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

    url = re.sub(
        r"[?&]+$",
        "",
        url,
    )

    return url.rstrip("/")


# =========================================================
# شناسه خبر و نسخه محتوا
# =========================================================

def create_news_id(item):
    link = normalize_url(item.get("link", ""))

    if link:
        base = "url:" + link
    else:
        title = normalize_text(item.get("title", ""))
        source = normalize_text(item.get("source", ""))
        base = f"title:{title}|source:{source}"

    return hashlib.sha256(
        base.encode("utf-8")
    ).hexdigest()


def create_content_hash(item):
    content = "\n".join([
        clean_text(item.get("title", "")),
        clean_text(item.get("summary", "")),
        clean_text(item.get("full_text", "")),
        clean_text(item.get("source", "")),
        normalize_url(item.get("link", "")),
    ])

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


# =========================================================
# بررسی ارتباط با بازار
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


MARKET_TERMS = [
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
    "بازار سهام",
    "شاخص بورس",
    "نیم سکه",
    "ربع سکه",
    "سکه امامی",
]


def has_market_evidence(item):
    for field in MARKET_FIELDS:
        value = item.get(field)

        if isinstance(value, dict) and value:
            return True

        if isinstance(value, (list, tuple, set)) and value:
            return True

    # بررسی عنوان، خلاصه و متن کامل
    title = normalize_text(item.get("title", ""))
    summary = normalize_text(item.get("summary", ""))
    full_text = normalize_text(item.get("full_text", ""))

    text = f"{title} {summary} {full_text}"

    return any(
        normalize_text(term) in text
        for term in MARKET_TERMS
    )


def is_promotional(item):
    title = normalize_text(item.get("title", ""))
    summary = normalize_text(item.get("summary", ""))
    full_text = normalize_text(item.get("full_text", ""))

    text = f"{title} {summary} {full_text}"

    matched = [
        pattern
        for pattern in PROMOTIONAL_PATTERNS
        if re.search(pattern, text)
    ]

    strong_commercial_terms = [
        "خرید دوره",
        "فروش دوره",
        "ثبت سفارش",
        "کد تخفیف",
        "سود تضمینی",
        "سیگنال تضمینی",
        "درآمد تضمینی",
    ]

    if any(term in text for term in strong_commercial_terms):
        return True

    # عبارت تبلیغاتی منفرد و مبهم کافی نیست.
    return len(matched) >= 2


def get_market_score(item):
    try:
        return float(item.get("market_score", 0))
    except (TypeError, ValueError):
        return 0.0


def is_publishable(item):
    priority = str(
        item.get("priority", "")
    ).strip().lower()

    if priority not in ("high", "medium"):
        return False

    if not has_market_evidence(item):
        return False

    minimum_score = 18 if priority == "high" else 9

    if get_market_score(item) < minimum_score:
        return False

    if is_promotional(item):
        return False

    if not clean_text(item.get("title", "")):
        return False

    if not normalize_url(item.get("link", "")):
        return False

    return True


# =========================================================
# ساخت متن خبر
# =========================================================

def build_news_body(item):
    title = clean_text(item.get("title", ""))

    # متن کامل بر خلاصه اولویت دارد.
    full_text = clean_text(item.get("full_text", ""))
    summary = clean_text(item.get("summary", ""))

    body = full_text or summary

    # اگر متن کامل و خلاصه متفاوت باشند،
    # خلاصه نیز حفظ می‌شود تا نکته‌ای از دست نرود.
    if full_text and summary:
        if normalize_text(full_text) != normalize_text(summary):
            if normalize_text(summary) not in normalize_text(full_text):
                body = full_text + "\n\nخلاصه خبر:\n" + summary

    source = clean_text(item.get("source", ""))
    link = normalize_url(item.get("link", ""))

    parts = [
        "🌙 زرین ماه | اخبار بازار",
        "",
        f"📰 {title}",
    ]

    if body:
        parts.extend([
            "",
            body,
        ])

    if source:
        parts.extend([
            "",
            f"📌 منبع: {source}",
        ])

    if link:
        parts.extend([
            "",
            f"🔗 مشاهده منبع:",
            link,
        ])

    parts.extend([
        "",
        "🌙 زرین ماه | طلای کم‌اجرت",
        "https://t.me/ZarinMahGold",
        "",
        "#اخبار_بازار",
    ])

    return "\n".join(parts)


# =========================================================
# تقسیم پیام بدون حذف متن
# =========================================================

def split_message(text, max_chars=MAX_PART_CHARS):
    text = str(text or "").strip()

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""

    def flush():
        nonlocal current

        if current.strip():
            chunks.append(current.strip())

        current = ""

    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()

        if not paragraph:
            if current and not current.endswith("\n"):
                current += "\n"
            continue

        while len(paragraph) > max_chars:
            if current:
                flush()

            cut = paragraph.rfind(
                " ",
                0,
                max_chars + 1,
            )

            if cut < max_chars // 2:
                cut = max_chars

            chunks.append(
                paragraph[:cut].strip()
            )

            paragraph = paragraph[cut:].strip()

        candidate = (
            current + "\n" + paragraph
            if current.strip()
            else paragraph
        )

        if len(candidate) <= max_chars:
            current = candidate
        else:
            flush()
            current = paragraph

    flush()

    return [
        chunk for chunk in chunks
        if chunk
    ]


def build_parts(item):
    message = build_news_body(item)
    chunks = split_message(message)

    if len(chunks) <= 1:
        return chunks

    total = len(chunks)
    result = []

    for index, chunk in enumerate(chunks, start=1):
        prefix = f"📄 بخش {index} از {total}\n\n"
        result.append(prefix + chunk)

    return result


# =========================================================
# ارسال تلگرام
# =========================================================

def send_to_telegram(
    message,
    chat_id=CHANNEL,
    message_thread_id=None,
):
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    url = (
        "https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": html.escape(message),
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
        "Telegram:",
        chat_id,
        "HTTP:",
        response.status_code,
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"خطای API تلگرام: {result}"
        )

    message_id = result.get(
        "result", {}
    ).get("message_id")

    if message_id is None:
        raise RuntimeError(
            "شناسه پیام از تلگرام دریافت نشد."
        )

    return message_id


# =========================================================
# ارسال ایتا
# =========================================================

def send_to_eitaa(message):
    if not EITAAYAR_TOKEN:
        raise RuntimeError(
            "EITAAYAR_TOKEN تنظیم نشده است."
        )

    if not EITAA_CHAT_ID:
        raise RuntimeError(
            "EITAA_CHAT_ID تنظیم نشده است."
        )

    token = EITAAYAR_TOKEN.strip()
    chat_id = EITAA_CHAT_ID.strip()

    url = f"{EITAA_API_URL}/{token}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": message,
        },
        timeout=REQUEST_TIMEOUT,
    )

    print(
        "Eitaa HTTP:",
        response.status_code,
    )

    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as error:
        raise RuntimeError(
            "پاسخ ایتا JSON معتبر نیست."
        ) from error

    if not result.get("ok"):
        raise RuntimeError(
            f"خطای API ایتا: {result}"
        )

    result_data = result.get("result", {})

    message_id = (
        result_data.get("message_id")
        or result_data.get("id")
    )

    # API ممکن است موفقیت را بدون شناسه اعلام کند.
    # در این حالت ثبت «sent» از تلاش فوری مجدد جلوگیری می‌کند.
    return message_id if message_id is not None else "sent"


# =========================================================
# وضعیت ناشر
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

    save_json_file(
        PUBLISHED_FILE,
        published,
    )

    return initialized_at, True


def ensure_record(published, news_id, item):
    record = published.get(news_id, {})

    if not isinstance(record, dict):
        record = {}

    record.setdefault(
        "title",
        item.get("title", ""),
    )

    record.setdefault(
        "source",
        item.get("source", ""),
    )

    record.setdefault(
        "link",
        item.get("link", ""),
    )

    for destination in (
        "telegram",
        "eitaa",
        "group",
    ):
        ids_key = f"{destination}_message_ids"
        legacy_key = f"{destination}_message_id"

        if not isinstance(record.get(ids_key), list):
            old_id = record.get(legacy_key)

            record[ids_key] = (
                [old_id]
                if old_id is not None
                else []
            )

    published[news_id] = record

    return record


def save_record(published, news_id, record):
    published[news_id] = record

    save_json_file(
        PUBLISHED_FILE,
        published,
    )


def has_any_delivery(record):
    for destination in (
        "telegram",
        "eitaa",
        "group",
    ):
        ids = record.get(
            f"{destination}_message_ids",
            [],
        )

        if isinstance(ids, list) and any(
            value is not None for value in ids
        ):
            return True

    return False


def is_fully_published(record, expected_parts):
    for destination in (
        "telegram",
        "eitaa",
        "group",
    ):
        ids = record.get(
            f"{destination}_message_ids",
            [],
        )

        if not isinstance(ids, list):
            return False

        if len(ids) < expected_parts:
            return False

        if any(
            value is None
            for value in ids[:expected_parts]
        ):
            return False

    return True


# =========================================================
# ارسال بخش‌ها با ذخیره وضعیت هر پیام
# =========================================================

def send_parts_to_destination(
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

    if not isinstance(sent_ids, list):
        raise RuntimeError(
            f"وضعیت {destination} نامعتبر است."
        )

    while len(sent_ids) < len(parts):
        sent_ids.append(None)

    for index, part in enumerate(parts):
        if sent_ids[index] is not None:
            continue

        print(
            f"Sending {destination}: "
            f"{index + 1}/{len(parts)}"
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
                message_thread_id=(
                    thread_id
                    if thread_id is not None
                    else NEWS_THREAD_ID
                ),
            )

        elif destination == "eitaa":
            message_id = send_to_eitaa(part)

        else:
            raise ValueError(
                f"مقصد ناشناخته: {destination}"
            )

        sent_ids[index] = message_id

        record[ids_key] = sent_ids
        record[f"{destination}_last_sent_at"] = now_iso()

        if index == 0:
            record[
                f"{destination}_message_id"
            ] = message_id

        save_record(
            published,
            news_id,
            record,
        )

    return True


# =========================================================
# اجرای اصلی
# =========================================================

def main():
    print("===================================")
    print("ZarinMah News Publisher")
    print("===================================")

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    if not EITAAYAR_TOKEN:
        raise RuntimeError(
            "EITAAYAR_TOKEN تنظیم نشده است."
        )

    if not EITAA_CHAT_ID:
        raise RuntimeError(
            "EITAA_CHAT_ID تنظیم نشده است."
        )

    # فایل ورودی باید موجود و معتبر باشد.
    # در صورت خطا، خروجی وضعیت را خالی نمی‌کنیم.
    news = load_json_file(
        INPUT_FILE,
        [],
        required=True,
    )

    if not isinstance(news, list):
        raise RuntimeError(
            f"{INPUT_FILE} باید یک فهرست JSON باشد."
        )

    published = load_json_file(
        PUBLISHED_FILE,
        {},
    )

    if not isinstance(published, dict):
        raise RuntimeError(
            f"{PUBLISHED_FILE} باید یک شیء JSON باشد."
        )

    initialized_at, first_run = initialize_publisher(
        published
    )

    if first_run:
        print("ناشر برای اولین بار راه‌اندازی شد.")
        print(
            "خبرهای آرشیوی قبل از زمان راه‌اندازی "
            "به‌صورت خودکار منتشر نمی‌شوند."
        )
        return

    print(
        "Initialized at:",
        initialized_at.isoformat(),
    )

    eligible_news = [
        item
        for item in news
        if isinstance(item, dict)
        and is_publishable(item)
    ]

    eligible_news.sort(
        key=lambda item: (
            get_collected_datetime(item).timestamp()
            if get_collected_datetime(item)
            else 0
        )
    )

    print("Total ready news:", len(news))
    print("Eligible news:", len(eligible_news))

    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for item in eligible_news:
        news_id = create_news_id(item)
        content_hash = create_content_hash(item)

        record = ensure_record(
            published,
            news_id,
            item,
        )

        existing_hash = record.get("content_hash")

        # اگر قبلاً ارسال شروع شده و محتوا تغییر کرده باشد،
        # ادامه نسخه جدید را با بخش‌های نسخه قبلی ترکیب نمی‌کنیم.
        if (
            existing_hash
            and existing_hash != content_hash
            and has_any_delivery(record)
        ):
            print(
                "Skipping changed content to prevent mixed or "
                "duplicate publication:",
                item.get("title", ""),
            )
            skipped_count += 1
            continue

        if not existing_hash:
            record["content_hash"] = content_hash

        collected_at = get_collected_datetime(item)

        # بدون تاریخ معتبر نمی‌توان تشخیص داد خبر آرشیوی است یا جدید.
        if collected_at is None:
            print(
                "Skipping news without a valid collection/publication date:",
                item.get("title", ""),
            )
            skipped_count += 1
            continue

        # جلوگیری از انتشار آرشیو هنگام اولین راه‌اندازی
        if collected_at.timestamp() <= initialized_at.timestamp():
            if not has_any_delivery(record):
                skipped_count += 1
                continue

        parts = build_parts(item)

        if not parts:
            skipped_count += 1
            continue

        if is_fully_published(record, len(parts)):
            skipped_count += 1
            continue

        record["expected_parts"] = len(parts)
        record["content_hash"] = content_hash

        save_record(
            published,
            news_id,
            record,
        )

        print()
        print("Publishing:", item.get("title", ""))
        print("Priority:", item.get("priority"))
        print("Market score:", item.get("market_score"))
        print("Parts:", len(parts))

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
                print("Publication completed.")
            else:
                failed_count += 1
                print("Publication incomplete.")

        except Exception as error:
            failed_count += 1

            print(
                "Publishing failed:",
                item.get("title", ""),
                str(error),
            )

            save_record(
                published,
                news_id,
                record,
            )

    print()
    print("===================================")
    print("Publishing finished")
    print("===================================")
    print("Published:", sent_count)
    print("Skipped:", skipped_count)
    print("Failed or incomplete:", failed_count)

    if failed_count:
        raise RuntimeError(
            f"{failed_count} publication(s) failed or remain incomplete."
        )


if __name__ == "__main__":
    main()
