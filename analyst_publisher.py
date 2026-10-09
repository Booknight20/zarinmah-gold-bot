import html
import json
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


TEHRAN_TZ = ZoneInfo("Asia/Tehran")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
EITAAYAR_TOKEN = os.environ.get("EITAAYAR_TOKEN", "").strip()
EITAA_CHAT_ID = os.environ.get("EITAA_CHAT_ID", "").strip().lstrip("@")
TELEGRAM_CHANNEL = "@ZarinMahGold"
READY_FILE = "analyst_ready.json"
PUBLISHED_FILE = "analyst_published.json"

SEPARATOR = "━━━━━━━━━━━━━━━━━━"


def now_iso():
    return datetime.now(TEHRAN_TZ).isoformat()


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data
    except Exception as error:
        print(f"Could not read {path}:", error)
        return default


def save_json(path, data):
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def prepare_published_state():
    """فرمت قبلی فایل وضعیت را تا جای ممکن حفظ می‌کند."""
    data = load_json(PUBLISHED_FILE, {})

    if isinstance(data, list):
        mapped = {}
        for item in data:
            if isinstance(item, dict):
                key = item.get("link") or item.get("key")
                if key:
                    mapped[str(key)] = item
        data = {"items": mapped}

    if not isinstance(data, dict):
        data = {}

    for container_name in ("items", "published", "posts", "analyses"):
        if isinstance(data.get(container_name), dict):
            return data, data[container_name], container_name

    # اگر فایل قدیمی مستقیماً با لینک پست‌ها کلیدگذاری شده،
    # همان قالب را حفظ می‌کنیم.
    looks_like_record_map = any(
        isinstance(value, dict)
        and any(
            key in value
            for key in (
                "telegram_message_id", "eitaa_message_id",
                "telegram_sent_at", "eitaa_sent_at",
                "item", "telegram_sent", "eitaa_sent",
            )
        )
        for value in data.values()
    )

    if looks_like_record_map or not data:
        return data, data, None

    # متادیتای یک فایل قدیمی را نگه می‌داریم و آیتم‌ها را در items ذخیره می‌کنیم.
    data["items"] = {}
    return data, data["items"], "items"


def published_is_sent(record, destination):
    return bool(
        record.get(f"{destination}_sent")
        or record.get(f"{destination}_message_id")
        or record.get(f"{destination}_sent_at")
    )


def item_key(item):
    link = str(item.get("link", "")).strip()
    if link:
        return link

    analyst = str(
        item.get("analyst") or item.get("source") or "تحلیلگر"
    ).strip()
    title = str(item.get("title", "")).strip()
    collected_at = str(item.get("collected_at", "")).strip()
    return f"{analyst}|{title}|{collected_at}"


def clean_display_text(value, fallback=""):
    text = str(value or fallback).strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def compact_telegram_link(link):
    """لینک پست تلگرام را بدون پارامترهای اضافه کوتاه و استاندارد می‌کند."""
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
        dt = dt.astimezone(TEHRAN_TZ)
        return dt.strftime("%Y/%m/%d - %H:%M")
    except Exception:
        return str(value)


def get_topics(item):
    matches = item.get("market_matches", [])
    if not isinstance(matches, list):
        return []

    result = []
    seen = set()

    for value in matches:
        topic = clean_display_text(value)
        normalized = topic.replace("‌", " ").strip().lower()
        if topic and normalized not in seen:
            seen.add(normalized)
            result.append(topic)
        if len(result) >= 5:
            break

    return result


def build_telegram_message(item):
    analyst = clean_display_text(
        item.get("analyst") or item.get("source"),
        "تحلیلگر بازار",
    )
    title = clean_display_text(
        item.get("title"),
        "مرور دیدگاه جدید بازار",
    )
    summary = clean_display_text(
        item.get("summary"),
        "چکیده‌ای از متن اصلی در دسترس نیست.",
    )
    link = compact_telegram_link(item.get("link"))
    collected_at = format_collected_at(item.get("collected_at"))
    topics = get_topics(item)

    parts = [
        "🌙✨ <b>زرین ماه | دیدگاه تحلیلگران</b>",
        SEPARATOR,
        f"👤 <b>تحلیلگر:</b> {html.escape(analyst)}",
        f"🧭 <b>موضوع:</b> {html.escape(title)}",
    ]

    if topics:
        parts.append(
            "🔎 <b>محورهای مطرح‌شده:</b> "
            + " • ".join(html.escape(x) for x in topics)
        )

    parts.extend([
        SEPARATOR,
        "📝 <b>چکیده دیدگاه</b>",
        html.escape(summary),
        SEPARATOR,
    ])

    if link:
        parts.append(
            f'🔗 <a href="{html.escape(link, quote=True)}">'
            "مشاهده پست اصلی</a>"
        )

    if collected_at:
        parts.append(
            f"🕒 <b>زمان دریافت:</b> {html.escape(collected_at)}"
        )

    parts.extend([
        "⚠️ <i>این مطلب بازتاب دیدگاه تحلیلگر منبع است و توصیه خریدوفروش زرین ماه نیست.</i>",
        "",
        "🌙 <b>زرین ماه</b> | ویترین طلای کم‌اجرت",
        "📲 @ZarinMahGold",
    ])

    return "\n\n".join(parts)


def build_eitaa_message(item):
    analyst = clean_display_text(
        item.get("analyst") or item.get("source"),
        "تحلیلگر بازار",
    )
    title = clean_display_text(
        item.get("title"),
        "مرور دیدگاه جدید بازار",
    )
    summary = clean_display_text(
        item.get("summary"),
        "چکیده‌ای از متن اصلی در دسترس نیست.",
    )
    link = compact_telegram_link(item.get("link"))
    collected_at = format_collected_at(item.get("collected_at"))
    topics = get_topics(item)

    parts = [
        "🌙✨ زرین ماه | دیدگاه تحلیلگران",
        SEPARATOR,
        f"👤 تحلیلگر: {analyst}",
        f"🧭 موضوع: {title}",
    ]

    if topics:
        parts.append(
            "🔎 محورهای مطرح‌شده: " + " • ".join(topics)
        )

    parts.extend([
        SEPARATOR,
        "📝 چکیده دیدگاه",
        summary,
        SEPARATOR,
    ])

    if link:
        parts.append(f"🔗 پست اصلی: {link}")

    if collected_at:
        parts.append(f"🕒 زمان دریافت: {collected_at}")

    parts.extend([
        "⚠️ این مطلب بازتاب دیدگاه تحلیلگر منبع است و توصیه خریدوفروش زرین ماه نیست.",
        "",
        "🌙 زرین ماه | ویترین طلای کم‌اجرت",
        "📲 @ZarinMahGold",
    ])

    return "\n\n".join(parts)


def send_to_telegram(item):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است.")

    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHANNEL,
            "text": build_telegram_message(item),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")

    return result.get("result", {}).get("message_id")


def send_to_eitaa(item):
    if not EITAAYAR_TOKEN:
        raise RuntimeError("EITAAYAR_TOKEN تنظیم نشده است.")
    if not EITAA_CHAT_ID:
        raise RuntimeError("EITAA_CHAT_ID تنظیم نشده است.")

    response = requests.post(
        f"https://eitaayar.ir/api/{EITAAYAR_TOKEN}/sendMessage",
        data={
            "chat_id": EITAA_CHAT_ID,
            "text": build_eitaa_message(item),
        },
        timeout=30,
    )
    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as error:
        raise RuntimeError(
            "Eitaa API پاسخ JSON معتبر برنگرداند."
        ) from error

    if not result.get("ok"):
        raise RuntimeError(f"Eitaa API error: {result}")

    payload = result.get("result", {})
    if isinstance(payload, dict):
        return payload.get("message_id") or payload.get("id")

    return result.get("message_id")


def main():
    print("===================================")
    print("ZarinMah Analyst Publisher")
    print("===================================")

    ready_data = load_json(READY_FILE, [])
    if not isinstance(ready_data, list):
        raise RuntimeError(
            f"{READY_FILE} باید شامل یک فهرست JSON باشد."
        )

    state, published, container_name = prepare_published_state()

    # علاوه بر آیتم‌های جدید، تحلیل‌هایی که ارسالشان در اجرای قبلی ناقص مانده
    # نیز از analyst_published.json دوباره امتحان می‌شوند.
    work = {}

    for item in ready_data:
        if isinstance(item, dict):
            work[item_key(item)] = item

    for key, record in list(published.items()):
        if not isinstance(record, dict):
            continue

        stored_item = record.get("item")
        if isinstance(stored_item, dict) and not (
            published_is_sent(record, "telegram")
            and published_is_sent(record, "eitaa")
        ):
            work.setdefault(str(key), stored_item)

    if not work:
        print("No new or pending analyst summaries to publish.")
        return

    errors = []

    for key, item in work.items():
        record = published.get(key)

        if not isinstance(record, dict):
            record = {}
            published[key] = record

        # نسخه کامل آیتم ذخیره می‌شود تا در صورت خطای ارسال قابل تلاش مجدد باشد.
        record["item"] = item
        record.setdefault("first_seen_at", now_iso())

        print(
            "\nPublishing:",
            item.get("analyst", "تحلیلگر"),
            "|",
            item.get("title", ""),
        )

        if not published_is_sent(record, "telegram"):
            try:
                message_id = send_to_telegram(item)
                record["telegram_sent"] = True
                record["telegram_sent_at"] = now_iso()

                if message_id is not None:
                    record["telegram_message_id"] = message_id

                print("Telegram: SENT")

            except Exception as error:
                errors.append(f"Telegram / {key}: {error}")
                print("Telegram: FAILED:", error)

            finally:
                save_json(PUBLISHED_FILE, state)

        else:
            print("Telegram: already sent; skipping duplicate.")

        if not published_is_sent(record, "eitaa"):
            try:
                message_id = send_to_eitaa(item)
                record["eitaa_sent"] = True
                record["eitaa_sent_at"] = now_iso()

                if message_id is not None:
                    record["eitaa_message_id"] = message_id

                print("Eitaa: SENT")

            except Exception as error:
                errors.append(f"Eitaa / {key}: {error}")
                print("Eitaa: FAILED:", error)

            finally:
                save_json(PUBLISHED_FILE, state)

        else:
            print("Eitaa: already sent; skipping duplicate.")

        if (
            published_is_sent(record, "telegram")
            and published_is_sent(record, "eitaa")
        ):
            record["published_at"] = record.get("published_at") or now_iso()

        save_json(PUBLISHED_FILE, state)

    if errors:
        print("\nSome analyst posts could not be published:")
        for error in errors:
            print("-", error)
        sys.exit(1)

    print("\nAll analyst summaries are published to Telegram and Eitaa.")


if __name__ == "__main__":
    main()
