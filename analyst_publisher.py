
import html
import json
import os
import re
import sys
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
        print(f"Could not read {path}: {error}")
        return default


def save_json(path, data):
    temporary = f"{path}.tmp"

    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    os.replace(temporary, path)


def clean_text(value, fallback=""):
    text = str(value or fallback).strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
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
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TEHRAN_TZ)

        return dt.astimezone(TEHRAN_TZ).strftime("%Y/%m/%d - %H:%M")

    except Exception:
        return str(value)


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

    return f"{analyst}|{title}|{collected_at}"


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

            key = link or record.get("link") or record.get("key")

            if key:
                mapped[str(key)] = record

        return {"items": mapped}, mapped

    if not isinstance(data, dict):
        data = {}

    for container_name in ("items", "published", "posts", "analyses"):
        if isinstance(data.get(container_name), dict):
            return data, data[container_name]

    looks_like_record_map = any(
        isinstance(value, dict)
        and any(
            key in value
            for key in (
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
    """
    وضعیت هر بخش را آماده می‌کند.

    اگر رکورد قدیمی وضعیت ارسال موفق داشته باشد و آرایه بخش‌ها
    وجود نداشته باشد، برای جلوگیری از انتشار دوباره به آن دست نمی‌زنیم.

    اگر آرایه بخش‌ها وجود داشته باشد اما تعداد بخش‌های متن تغییر کرده
    باشد، وضعیت بخش‌های قبلی حفظ می‌شود و بخش‌های تازه False می‌مانند.
    """
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

    # سازگاری با وضعیت قدیمی که فقط یک پرچم ارسال داشت.
    if destination_is_sent(record, destination):
        return

    record[sent_key] = [False] * total
    record[ids_key] = [None] * total


def find_existing_record(item, published):
    """
    رکورد را با کلید استاندارد پیدا می‌کند.
    اگر کلید قدیمی متفاوت باشد، لینک داخل item هم بررسی می‌شود.
    """
    key = item_key(item)

    if isinstance(published.get(key), dict):
        return key, published[key]

    wanted_link = compact_telegram_link(item.get("link"))

    if wanted_link:
        for old_key, record in list(published.items()):
            if not isinstance(record, dict):
                continue

            stored_item = record.get("item")

            if not isinstance(stored_item, dict):
                continue

            stored_link = compact_telegram_link(stored_item.get("link"))

            if stored_link == wanted_link:
                # رکورد قدیمی را به کلید استاندارد منتقل می‌کنیم.
                if old_key != key:
                    if key not in published:
                        published[key] = record

                    published.pop(old_key, None)

                return key, record

    record = {}
    published[key] = record
    return key, record


# =========================================================
# تقسیم متن بدون حذف محتوا
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
    collected_at = format_collected_at(item.get("collected_at"))
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
            lines.append("🔎 محورهای مطرح‌شده: " + " • ".join(topics))

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
            "⚠️ این مطلب بازتاب دیدگاه تحلیلگر منبع است و توصیه خریدوفروش زرین ماه نیست.",
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
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است.")

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
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")

    return result.get("result", {}).get("message_id")


# =========================================================
# ارسال ایتا
# =========================================================

def send_to_eitaa(text):
    if not EITAAYAR_TOKEN:
        raise RuntimeError("EITAAYAR_TOKEN تنظیم نشده است.")

    if not EITAA_CHAT_ID:
        raise RuntimeError("EITAA_CHAT_ID تنظیم نشده است.")

    response = requests.post(
        f"https://eitaayar.ir/api/{EITAAYAR_TOKEN}/sendMessage",
        data={
            "chat_id": EITAA_CHAT_ID,
            "text": text,
        },
        timeout=30,
    )
    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as error:
        raise RuntimeError("پاسخ ایتا JSON معتبر نیست.") from error

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
    initialize_parts(record, destination, len(messages))

    sent_key = f"{destination}_parts_sent"
    ids_key = f"{destination}_part_message_ids"

    # وضعیت قدیمی ارسال موفق، بدون آرایه بخش‌ها
    if destination_is_sent(record, destination):
        if not isinstance(record.get(sent_key), list):
            print(f"{destination}: already sent; skipping.")
            return

    # اطمینان از سازگاری آرایه‌ها با تعداد بخش‌ها
    if not isinstance(record.get(sent_key), list):
        record[sent_key] = [False] * len(messages)

    if not isinstance(record.get(ids_key), list):
        record[ids_key] = [None] * len(messages)

    if len(record[sent_key]) != len(messages):
        initialize_parts(record, destination, len(messages))

    for index, message in enumerate(messages):
        if record[sent_key][index]:
            continue

        try:
            message_id = send_function(message)

            record[sent_key][index] = True
            record[ids_key][index] = message_id
            record[f"{destination}_last_success_at"] = now_iso()

            print(
                f"{destination}: part {index + 1}/{len(messages)} SENT"
            )

            # بعد از هر بخش ذخیره می‌کنیم تا در اجرای بعدی ادامه دهد.
            save_json(PUBLISHED_FILE, state)

        except Exception as error:
            print(
                f"{destination}: part {index + 1}/{len(messages)} "
                f"FAILED: {error}"
            )

            record.setdefault("errors", []).append({
                "destination": destination,
                "part": index + 1,
                "time": now_iso(),
                "error": str(error),
            })

            save_json(PUBLISHED_FILE, state)
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

    # ادغام موارد آماده فعلی با مواردی که انتشارشان ناقص مانده است.
    work = {}

    for item in ready_data:
        if not isinstance(item, dict):
            continue

        key = item_key(item)

        if key not in work:
            work[key] = item

    for _, record in list(published.items()):
        if not isinstance(record, dict):
            continue

        stored_item = record.get("item")

        if not isinstance(stored_item, dict):
            continue

        complete = all(
            destination_is_sent(record, destination)
            for destination in ("telegram", "eitaa", "group")
        )

        if not complete:
            key = item_key(stored_item)
            work.setdefault(key, stored_item)

    if not work:
        print("No new or pending analyst posts to publish.")
        return

    errors = []

    for _, item in work.items():
        key, record = find_existing_record(item, published)

        record["item"] = item
        record.setdefault("first_seen_at", now_iso())

        print(
            "\nPublishing:",
            item.get("analyst") or item.get("source") or "تحلیلگر",
            "|",
            item.get("title", ""),
            "|",
            key,
        )

        # کانال تلگرام
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
            record["published_at"] = record.get("published_at") or now_iso()
            print("Analysis fully published to all destinations.")
        else:
            print("Analysis remains pending in publication state.")

        save_json(PUBLISHED_FILE, state)

    if errors:
        print("\nSome analyst posts could not be fully published:")

        for error in errors:
            print("-", error)

        # اجرای بعدی باید بتواند بخش‌های ناموفق را دوباره امتحان کند.
        sys.exit(1)

    print(
        "\nAll pending analyst posts have been processed "
        "for Telegram channel, group topic, and Eitaa."
    )


if __name__ == "__main__":
    main()
