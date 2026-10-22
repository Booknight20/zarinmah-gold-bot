```python
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


# =========================================================
# تنظیمات
# =========================================================

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
EITAAYAR_TOKEN = os.environ.get("EITAAYAR_TOKEN", "").strip()
EITAA_CHAT_ID = os.environ.get("EITAA_CHAT_ID", "").strip().lstrip("@")

TELEGRAM_CHANNEL = "@ZarinMahGold"
TELEGRAM_GROUP = "@ZarinMahCommunity"
ANALYST_THREAD_ID = 25

READY_FILE = "analyst_ready.json"
PUBLISHED_FILE = "analyst_published.json"

CONTENT_CHUNK_SIZE = 2200
SEPARATOR = "━━━━━━━━━━━━━━━━━━"
MAX_ERROR_HISTORY = 30
REQUEST_TIMEOUT = 30


# =========================================================
# ابزارهای عمومی
# =========================================================

def now_iso():
    return datetime.now(TEHRAN_TZ).isoformat()


def load_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    except Exception as error:
        raise RuntimeError(
            f"فایل {path} قابل خواندن نیست. "
            f"برای جلوگیری از ازدست‌رفتن وضعیت انتشار، "
            f"اجرا متوقف شد: {error}"
        ) from error


def save_json(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)

    fd, temporary_path = tempfile.mkstemp(
        prefix=".analyst_publisher_",
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


def clean_text(value, fallback=""):
    text = str(value or fallback).strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u0000", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def compact_telegram_link(link):
    link = str(link or "").strip()

    match = re.search(
        r"(?:https?://)?(?:www\.)?t\.me/([A-Za-z0-9_]+)/([0-9]+)",
        link,
    )

    if match:
        return f"https://t.me/{match.group(1)}/{match.group(2)}"

    return link


def format_collected_at(value):
    if not value:
        return ""

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TEHRAN_TZ)

        return dt.astimezone(TEHRAN_TZ).strftime(
            "%Y/%m/%d - %H:%M"
        )

    except Exception:
        return str(value)


def get_summary(item):
    for field in ("full_text", "summary", "text", "content"):
        value = clean_text(item.get(field))

        if value:
            return value

    return "متن تحلیل در منبع ذخیره نشده است."


def get_topics(item):
    matches = item.get("market_matches", [])

    if not isinstance(matches, list):
        return []

    result = []
    seen = set()

    for value in matches:
        topic = clean_text(value)
        normalized = topic.replace("‌", " ").lower().strip()

        if topic and normalized not in seen:
            seen.add(normalized)
            result.append(topic)

    return result


def item_key(item):
    link = compact_telegram_link(item.get("link"))

    if link:
        return link

    analyst = clean_text(
        item.get("analyst") or item.get("source"),
        "تحلیلگر",
    )
    title = clean_text(item.get("title"))
    collected_at = clean_text(item.get("collected_at"))

    raw = f"{analyst}|{title}|{collected_at}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    return f"fallback:{digest}"


def content_signature(item):
    """
    امضای محتوایی مستقل از زمان جمع‌آوری.

    تغییر زمان جمع‌آوری به‌تنهایی نباید باعث انتشار دوباره شود.
    تغییر متن، عنوان، تحلیلگر، لینک یا موضوع‌ها نسخه جدید محسوب می‌شود.
    """
    payload = {
        "analyst": clean_text(
            item.get("analyst") or item.get("source")
        ),
        "title": clean_text(item.get("title")),
        "text": get_summary(item),
        "link": compact_telegram_link(item.get("link")),
        "topics": get_topics(item),
    }

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


# =========================================================
# آماده‌سازی وضعیت انتشار
# =========================================================

def prepare_published_state():
    data = load_json(PUBLISHED_FILE, {})

    if isinstance(data, list):
        mapped = {}

        for record in data:
            if not isinstance(record, dict):
                continue

            item = record.get("item")
            link = ""

            if isinstance(item, dict):
                link = compact_telegram_link(item.get("link"))

            key = (
                link
                or record.get("link")
                or record.get("key")
            )

            if key:
                mapped[str(key)] = record

        return {"items": mapped}, mapped

    if not isinstance(data, dict):
        raise RuntimeError(
            f"{PUBLISHED_FILE} باید یک شیء یا فهرست JSON باشد."
        )

    for container_name in ("items", "published", "posts", "analyses"):
        if isinstance(data.get(container_name), dict):
            return data, data[container_name]

    looks_like_record_map = any(
        isinstance(value, dict)
        and any(
            field in value
            for field in (
                "telegram_message_id",
                "eitaa_message_id",
                "group_message_id",
                "telegram_sent",
                "eitaa_sent",
                "group_sent",
                "telegram_parts_sent",
                "eitaa_parts_sent",
                "group_parts_sent",
                "item",
            )
        )
        for value in data.values()
    )

    if looks_like_record_map or not data:
        return data, data

    data["items"] = {}
    return data, data["items"]


def destination_is_sent(record, destination):
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


def initialize_parts(record, destination, total):
    sent_key = f"{destination}_parts_sent"
    ids_key = f"{destination}_part_message_ids"

    existing_sent = record.get(sent_key)
    existing_ids = record.get(ids_key)

    if isinstance(existing_sent, list):
        sent = list(existing_sent[:total])
        sent.extend([False] * (total - len(sent)))

        if isinstance(existing_ids, list):
            ids = list(existing_ids[:total])
        else:
            ids = []

        ids.extend([None] * (total - len(ids)))

        record[sent_key] = sent
        record[ids_key] = ids
        return

    # سازگاری با رکوردهای قدیمی که فقط پرچم موفقیت دارند.
    if destination_is_sent(record, destination):
        return

    record[sent_key] = [False] * total
    record[ids_key] = [None] * total


def reset_destination_state(record, destination):
    """
    در صورت تغییر واقعی محتوای تحلیل، وضعیت ارسال نسخه قبلی
    برای هر مقصد پاک می‌شود تا نسخه جدید منتشر شود.
    پیام‌های قدیمی در مقصد حذف نمی‌شوند.
    """
    for suffix in (
        "sent",
        "sent_at",
        "message_id",
        "last_success_at",
    ):
        record.pop(f"{destination}_{suffix}", None)

    record[f"{destination}_parts_sent"] = []
    record[f"{destination}_part_message_ids"] = []


def find_existing_record(item, published):
    key = item_key(item)

    if isinstance(published.get(key), dict):
        return key, published[key]

    wanted_link = compact_telegram_link(item.get("link"))

    if wanted_link:
        for old_key, record in list(published.items()):
            if not isinstance(record, dict):
                continue

            stored_item = record.get("item")

            stored_link = ""

            if isinstance(stored_item, dict):
                stored_link = compact_telegram_link(
                    stored_item.get("link")
                )

            if not stored_link:
                stored_link = compact_telegram_link(
                    record.get("link")
                )

            if stored_link == wanted_link:
                if old_key != key:
                    if key not in published:
                        published[key] = record

                    published.pop(old_key, None)

                return key, record

    record = {}
    published[key] = record

    return key, record


# =========================================================
# تقسیم متن بدون حذف محتوای اصلی
# =========================================================

def split_text(text, max_chars=CONTENT_CHUNK_SIZE):
    text = str(text or "")

    if not text:
        return ["متنی برای نمایش موجود نیست."]

    chunks = []

    while len(text) > max_chars:
        cut = text.rfind("\n\n", 0, max_chars + 1)

        if cut < max_chars // 2:
            cut = text.rfind("\n", 0, max_chars + 1)

        if cut < max_chars // 2:
            cut = text.rfind(" ", 0, max_chars + 1)

        if cut < 1:
            cut = max_chars

        chunk = text[:cut].strip()

        if chunk:
            chunks.append(chunk)

        text = text[cut:].lstrip()

    if text:
        chunks.append(text)

    return chunks or ["متنی برای نمایش موجود نیست."]


def build_message_parts(item):
    analyst = clean_text(
        item.get("analyst") or item.get("source"),
        "تحلیلگر بازار",
    )

    title = clean_text(
        item.get("title"),
        "مرور دیدگاه جدید بازار",
    )

    summary = get_summary(item)
    link = compact_telegram_link(item.get("link"))
    collected_at = format_collected_at(
        item.get("collected_at")
    )
    topics = get_topics(item)

    chunks = split_text(summary)
    total = len(chunks)
    messages = []

    for index, chunk in enumerate(chunks, start=1):
        lines = [
            "🌙✨ زرین ماه | دیدگاه تحلیلگران",
            SEPARATOR,
            f"👤 تحلیلگر: {analyst}",
            f"🧭 موضوع: {title}",
        ]

        if topics:
            lines.append(
                "🔎 محورهای مطرح‌شده: " + " • ".join(topics)
            )

        lines.extend([
            SEPARATOR,
            f"📝 متن تحلیل — بخش {index} از {total}",
            chunk,
            SEPARATOR,
        ])

        if link:
            lines.append(f"🔗 مشاهده پست اصلی: {link}")

        if collected_at:
            lines.append(f"🕒 زمان دریافت: {collected_at}")

        lines.extend([
            "⚠️ این مطلب بازتاب دیدگاه تحلیلگر منبع است "
            "و توصیه خریدوفروش زرین ماه نیست.",
            "",
            "🌙 زرین ماه | ویترین طلای کم‌اجرت",
            "📲 @ZarinMahGold",
            "#قیمت_و_تحلیل",
        ])

        messages.append("\n\n".join(lines))

    return messages


# =========================================================
# ارسال تلگرام
# =========================================================

def send_to_telegram(
    text,
    chat_id=TELEGRAM_CHANNEL,
    message_thread_id=None,
):
    if not BOT_TOKEN:
        raise RuntimeError(
            "متغیر TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    if message_thread_id is not None:
        payload["message_thread_id"] = message_thread_id

    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as error:
        raise RuntimeError(
            "پاسخ تلگرام JSON معتبر نیست."
        ) from error

    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")

    return result.get("result", {}).get("message_id")


# =========================================================
# ارسال ایتا
# =========================================================

def send_to_eitaa(text):
    if not EITAAYAR_TOKEN:
        raise RuntimeError(
            "متغیر EITAAYAR_TOKEN تنظیم نشده است."
        )

    if not EITAA_CHAT_ID:
        raise RuntimeError(
            "متغیر EITAA_CHAT_ID تنظیم نشده است."
        )

    response = requests.post(
        f"https://eitaayar.ir/api/{EITAAYAR_TOKEN}/sendMessage",
        data={
            "chat_id": EITAA_CHAT_ID,
            "text": text,
        },
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as error:
        raise RuntimeError(
            "پاسخ ایتا JSON معتبر نیست."
        ) from error

    if not result.get("ok"):
        raise RuntimeError(f"Eitaa API error: {result}")

    payload = result.get("result", {})

    if isinstance(payload, dict):
        return payload.get("message_id") or payload.get("id")

    return result.get("message_id")


# =========================================================
# انتشار بخش‌ها و ثبت وضعیت
# =========================================================

def publish_parts(
    item,
    record,
    destination,
    send_function,
    state,
):
    messages = build_message_parts(item)

    initialize_parts(
        record,
        destination,
        len(messages),
    )

    sent_key = f"{destination}_parts_sent"
    ids_key = f"{destination}_part_message_ids"

    # رکورد قدیمی ممکن است فقط یک پرچم موفقیت داشته باشد.
    if destination_is_sent(record, destination):
        if not isinstance(record.get(sent_key), list):
            print(
                f"{destination}: قبلاً ارسال شده؛ "
                "برای جلوگیری از تکرار رد شد."
            )
            return

    if not isinstance(record.get(sent_key), list):
        record[sent_key] = [False] * len(messages)

    if not isinstance(record.get(ids_key), list):
        record[ids_key] = [None] * len(messages)

    # آرایه‌ها باید دقیقاً با تعداد بخش‌های فعلی هماهنگ باشند.
    if len(record[sent_key]) != len(messages):
        initialize_parts(
            record,
            destination,
            len(messages),
        )

    for index, message in enumerate(messages):
        if record[sent_key][index]:
            print(
                f"{destination}: بخش {index + 1} "
                "قبلاً ثبت شده؛ رد شد."
            )
            continue

        try:
            message_id = send_function(message)

            record[sent_key][index] = True
            record[ids_key][index] = message_id
            record[f"{destination}_last_success_at"] = now_iso()

            print(
                f"{destination}: بخش "
                f"{index + 1}/{len(messages)} ارسال شد."
            )

            # ذخیره بلافاصله پس از هر بخش موفق
            save_json(PUBLISHED_FILE, state)

        except Exception as error:
            error_entry = {
                "destination": destination,
                "part": index + 1,
                "time": now_iso(),
                "error": str(error),
            }

            history = record.setdefault("errors", [])
            history.append(error_entry)

            if len(history) > MAX_ERROR_HISTORY:
                record["errors"] = history[-MAX_ERROR_HISTORY:]

            save_json(PUBLISHED_FILE, state)

            print(
                f"{destination}: بخش {index + 1}/"
                f"{len(messages)} ناموفق بود: {error}"
            )

            raise

    if all(record[sent_key]):
        record[f"{destination}_sent"] = True
        record[f"{destination}_sent_at"] = now_iso()

        if record[ids_key]:
            first_id = record[ids_key][0]

            if first_id is not None:
                record[f"{destination}_message_id"] = first_id

        save_json(PUBLISHED_FILE, state)


# =========================================================
# اجرای اصلی
# =========================================================

def main():
    print("===================================")
    print("ZarinMah Analyst Publisher")
    print("===================================")

    ready_data = load_json(READY_FILE, [])

    if not isinstance(ready_data, list):
        raise RuntimeError(
            f"{READY_FILE} باید شامل یک فهرست JSON باشد."
        )

    state, published = prepare_published_state()

    # صف آماده فعلی
    work = {}

    for item in ready_data:
        if not isinstance(item, dict):
            continue

        key = item_key(item)

        if key not in work:
            work[key] = item

    # بازیابی مواردی که انتشارشان در اجرای قبلی ناقص مانده است.
    for _, record in list(published.items()):
        if not isinstance(record, dict):
            continue

        stored_item = record.get("item")

        if not isinstance(stored_item, dict):
            continue

        if not is_fully_published(record):
            key = item_key(stored_item)
            work.setdefault(key, stored_item)

    if not work:
        print("تحلیل جدید یا در انتظار انتشاری وجود ندارد.")
        return

    errors = []

    for _, item in work.items():
        key, record = find_existing_record(item, published)

        old_item = record.get("item")

        new_signature = content_signature(item)
        old_signature = (
            content_signature(old_item)
            if isinstance(old_item, dict)
            else ""
        )

        # اگر محتوای یک لینک تغییر کرده باشد، نسخه جدید باید منتشر شود.
        # زمان جمع‌آوری به‌تنهایی باعث انتشار دوباره نخواهد شد.
        if (
            isinstance(old_item, dict)
            and old_signature
            and new_signature != old_signature
        ):
            print(
                "تغییر محتوای تحلیل تشخیص داده شد؛ "
                "وضعیت ارسال نسخه قبلی بازنشانی می‌شود."
            )

            record.setdefault("revision_history", []).append({
                "content_signature": old_signature,
                "changed_at": now_iso(),
            })

            record["revision_history"] = (
                record["revision_history"][-5:]
            )

            for destination in (
                "telegram",
                "eitaa",
                "group",
            ):
                reset_destination_state(
                    record,
                    destination,
                )

            record["revision_count"] = (
                int(record.get("revision_count", 0)) + 1
            )

        record["item"] = item
        record["content_signature"] = new_signature
        record.setdefault("first_seen_at", now_iso())

        print(
            "\nدر حال انتشار:",
            item.get("analyst") or item.get("source") or "تحلیلگر",
            "|",
            item.get("title", ""),
            "|",
            key,
        )

        # کانال اصلی تلگرام
        try:
            publish_parts(
                item=item,
                record=record,
                destination="telegram",
                send_function=lambda message: send_to_telegram(
                    message,
                    chat_id=TELEGRAM_CHANNEL,
                ),
                state=state,
            )
        except Exception as error:
            errors.append(f"Telegram / {key}: {error}")

        # ایتا
        try:
            publish_parts(
                item=item,
                record=record,
                destination="eitaa",
                send_function=send_to_eitaa,
                state=state,
            )
        except Exception as error:
            errors.append(f"Eitaa / {key}: {error}")

        # تاپیک تحلیل‌های گروه تلگرام
        try:
            publish_parts(
                item=item,
                record=record,
                destination="group",
                send_function=lambda message: send_to_telegram(
                    message,
                    chat_id=TELEGRAM_GROUP,
                    message_thread_id=ANALYST_THREAD_ID,
                ),
                state=state,
            )
        except Exception as error:
            errors.append(f"Telegram group / {key}: {error}")

        complete = all(
            destination_is_sent(record, destination)
            for destination in ("telegram", "eitaa", "group")
        )

        if complete:
            record["published_at"] = (
                record.get("published_at") or now_iso()
            )
            print("انتشار تحلیل در هر سه مقصد تکمیل شد.")
        else:
            print("انتشار تحلیل ناقص است؛ برای تلاش مجدد نگه داشته شد.")

        save_json(PUBLISHED_FILE, state)

    if errors:
        print("\nبرخی تحلیل‌ها کامل منتشر نشدند:")

        for error in errors:
            print("-", error)

        sys.exit(1)

    print(
        "\nپردازش صف تحلیل‌ها برای کانال تلگرام، "
        "تاپیک گروه و ایتا به پایان رسید."
    )


if __name__ == "__main__":
    main()
```
