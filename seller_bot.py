
# -*- coding: utf-8 -*-
"""ZarinMahGold seller-submission bot.
Runs as a persistent long-polling process; use TELEGRAM_BOT_TOKEN env var.
"""
import html
import json
import os
import time
from pathlib import Path

import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_ID = 8816884849
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL", "@ZarinMahGold").strip()
API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
DATA_FILE = Path(os.getenv("SELLER_DATA_FILE", "seller_data.json"))
POLL_TIMEOUT = 30

FIELDS = [
    ("product_type", "نوع کالا را بنویسید؛ مثلاً انگشتر، دستبند، سکه یا طلای آب‌شده."),
    ("weight", "وزن کالا را به گرم وارد کنید. اگر وزن ندارد، بنویسید: ندارد"),
    ("purity", "عیار کالا را بنویسید؛ مثلاً ۱۸ عیار، ۲۴ عیار یا نامشخص."),
    ("price", "قیمت پیشنهادی را به تومان وارد کنید."),
    ("city", "شهر محل تحویل را بنویسید."),
    ("contact", "راه ارتباطی فروشنده را بنویسید؛ مثلاً آیدی تلگرام یا شماره‌ای که مایلید منتشر شود."),
    ("details", "توضیحات تکمیلی را بنویسید. اگر توضیحی ندارید، بنویسید: ندارد"),
    ("photo", "حالا عکس واضح کالا را به صورت عکس (Photo) ارسال کنید؛ فایل سندی نفرستید."),
]


def load_data():
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("states", {})
                data.setdefault("items", {})
                data.setdefault("next_id", 1)
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"states": {}, "items": {}, "next_id": 1}


def save_data():
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(DB, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA_FILE)


DB = load_data()


def api(method, payload=None, files=None, timeout=45):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is missing")
    try:
        response = requests.post(
            f"{API}/{method}",
            data=payload or {},
            files=files,
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(f"Telegram API request failed: {exc}") from exc
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")
    return result.get("result")


def send_text(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return api("sendMessage", payload)


def keyboard(is_admin=False):
    rows = [
        [{"text": "🛍 ثبت آگهی فروش طلا"}],
        [{"text": "ℹ️ راهنمای ثبت آگهی"}],
    ]
    if is_admin:
        rows = [
            [{"text": "💎 ثبت محصول خودم"}],
            [{"text": "📋 آگهی‌های در انتظار"}],
            *rows,
        ]
    return {"keyboard": rows, "resize_keyboard": True}


def start_flow(user_id, own_product=False):
    DB["states"][str(user_id)] = {
        "step": 0,
        "data": {},
        "own_product": own_product,
    }
    save_data()
    intro = (
        "ثبت محصول مدیر زرین ماه آغاز شد.\n\n"
        if own_product
        else "ثبت آگهی شما آغاز شد. پس از تکمیل اطلاعات، آگهی برای بررسی مدیر ارسال می‌شود.\n\n"
    )
    send_text(
        user_id,
        intro + FIELDS[0][1],
        keyboard(user_id == ADMIN_ID),
    )


def safe(value):
    return html.escape(str(value or "").strip())


def item_caption(item, item_id, preview=False):
    owner_label = (
        "محصول مدیر زرین ماه"
        if item.get("own_product")
        else "آگهی فروش کاربر"
    )
    lines = [
        "🌙 <b>زرین ماه | طلای کم‌اجرت</b>",
        f"💎 <b>{safe(item.get('product_type'))}</b>",
        f"⚖️ وزن: {safe(item.get('weight'))}",
        f"🔸 عیار: {safe(item.get('purity'))}",
        f"💰 قیمت پیشنهادی: {safe(item.get('price'))} تومان",
        f"📍 شهر: {safe(item.get('city'))}",
        f"📩 ارتباط: {safe(item.get('contact'))}",
    ]
    details = str(item.get("details", "")).strip()
    if details and details.lower() != "ندارد":
        lines.append(f"📝 توضیحات: {safe(details)}")
    lines.extend([
        f"🏷 نوع آگهی: {owner_label}",
        "",
        "#محصولات_برای_فروش",
        "📲 @ZarinMahGold",
    ])
    return "\n".join(lines)[:1000]


def send_photo(chat_id, photo_id, caption, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "photo": photo_id,
        "caption": caption,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return api("sendPhoto", payload)


def admin_review(item_id):
    item = DB["items"][str(item_id)]
    caption = (
        f"🆕 <b>آگهی شماره {item_id} برای بررسی</b>\n\n"
        + item_caption(item, item_id)
    )
    markup = {
        "inline_keyboard": [[
            {
                "text": "✅ تأیید و انتشار",
                "callback_data": f"approve:{item_id}",
            },
            {
                "text": "❌ رد آگهی",
                "callback_data": f"reject:{item_id}",
            },
        ]]
    }
    send_photo(ADMIN_ID, item["photo_id"], caption[:1000], markup)


def finish_submission(user_id, photo_id):
    state = DB["states"].get(str(user_id))
    if not state:
        return

    item_id = DB["next_id"]
    DB["next_id"] += 1

    item = dict(state.get("data", {}))
    item.update({
        "photo_id": photo_id,
        "seller_id": user_id,
        "own_product": bool(state.get("own_product")),
        "status": "pending",
        "created_at": int(time.time()),
    })

    DB["items"][str(item_id)] = item
    DB["states"].pop(str(user_id), None)
    save_data()

    if item["own_product"]:
        send_text(
            user_id,
            f"پیش‌نمایش محصول شماره {item_id} آماده شد. "
            "برای انتشار در کانال، آن را تأیید کن.",
        )
    else:
        send_text(
            user_id,
            f"آگهی شما با شماره {item_id} برای بررسی مدیر ارسال شد. "
            "پس از تأیید، در کانال منتشر می‌شود.",
            keyboard(False),
        )

    admin_review(item_id)


def process_message(message):
    chat = message.get("chat", {})
    user = message.get("from", {})
    chat_id = chat.get("id")
    user_id = user.get("id")

    if not chat_id or not user_id or chat.get("type") != "private":
        return

    text = (message.get("text") or "").strip()

    if text.startswith("/start"):
        welcome = (
            "🌙 به ربات زرین ماه خوش آمدید.\n\n"
            "برای ثبت آگهی فروش طلا از دکمه زیر استفاده کنید. "
            "آگهی کاربران فقط پس از بررسی مدیر منتشر می‌شود."
        )
        send_text(chat_id, welcome, keyboard(user_id == ADMIN_ID))
        return

    if text == "ℹ️ راهنمای ثبت آگهی":
        send_text(
            chat_id,
            "برای ثبت آگهی، عکس واضح و مشخصات درست کالا را وارد کنید. "
            "انتشار رایگان است و آگهی پس از بررسی مدیر منتشر می‌شود. "
            "از ارسال اطلاعات نادرست خودداری کنید.",
            keyboard(user_id == ADMIN_ID),
        )
        return

    if user_id == ADMIN_ID and text == "💎 ثبت محصول خودم":
        start_flow(user_id, True)
        return

    if user_id == ADMIN_ID and text == "📋 آگهی‌های در انتظار":
        pending = [
            key for key, value in DB["items"].items()
            if value.get("status") == "pending"
        ]
        if not pending:
            send_text(
                chat_id,
                "در حال حاضر آگهیِ در انتظار بررسی وجود ندارد.",
                keyboard(True),
            )
        else:
            send_text(
                chat_id,
                "آگهی‌های در انتظار: " + ", ".join(pending) +
                "\nبرای هر مورد، پیام بررسی شامل دکمه تأیید و رد برایت ارسال شده است.",
                keyboard(True),
            )
        return

    if text == "🛍 ثبت آگهی فروش طلا":
        start_flow(user_id, False)
        return

    state = DB["states"].get(str(user_id))
    if not state:
        send_text(
            chat_id,
            "برای شروع، /start را بزن و یکی از گزینه‌های منو را انتخاب کن.",
            keyboard(user_id == ADMIN_ID),
        )
        return

    step = int(state.get("step", 0))
    field_name, prompt = FIELDS[step]

    if field_name == "photo":
        photos = message.get("photo") or []
        if not photos:
            send_text(
                chat_id,
                "لطفاً عکس کالا را با گزینه Photo ارسال کن؛ سپس ثبت ادامه پیدا می‌کند.",
            )
            return
        finish_submission(user_id, photos[-1]["file_id"])
        return

    if not text:
        send_text(
            chat_id,
            "لطفاً پاسخ را به صورت متن بفرست.\n\n" + prompt,
        )
        return

    state["data"][field_name] = text
    state["step"] = step + 1
    DB["states"][str(user_id)] = state
    save_data()
    send_text(chat_id, FIELDS[step + 1][1])


def process_callback(callback):
    data = callback.get("data", "")
    from_user = callback.get("from", {})
    callback_id = callback.get("id")

    if from_user.get("id") != ADMIN_ID:
        api("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "این دکمه فقط برای مدیر است.",
            "show_alert": "true",
        })
        return

    try:
        action, item_id = data.split(":", 1)
        item = DB["items"].get(item_id)
    except ValueError:
        item = None
        action = ""
        item_id = ""

    if not item:
        api("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "آگهی پیدا نشد.",
        })
        return

    if item.get("status") != "pending":
        api("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "این آگهی قبلاً بررسی شده است.",
        })
        return

    if action == "approve":
        try:
            published = send_photo(
                CHANNEL_ID,
                item["photo_id"],
                item_caption(item, item_id),
            )
        except Exception as exc:
            api("answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "انتشار ناموفق بود؛ گزارش اجرا را بررسی کن.",
                "show_alert": "true",
            })
            print(f"Failed to publish item {item_id}: {exc}")
            return

        item["status"] = "published"
        item["channel_message_id"] = published.get("message_id")
        save_data()

        api("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "آگهی منتشر شد.",
        })
        send_text(ADMIN_ID, f"✅ آگهی شماره {item_id} در کانال منتشر شد.")

        if not item.get("own_product"):
            try:
                send_text(
                    item["seller_id"],
                    f"تبریک! آگهی شماره {item_id} پس از بررسی تأیید "
                    "و در کانال زرین ماه منتشر شد.",
                )
            except Exception as exc:
                print(f"Could not notify seller for item {item_id}: {exc}")

    elif action == "reject":
        item["status"] = "rejected"
        save_data()

        api("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "آگهی رد شد.",
        })
        send_text(ADMIN_ID, f"آگهی شماره {item_id} رد شد.")

        if not item.get("own_product"):
            try:
                send_text(
                    item["seller_id"],
                    f"آگهی شماره {item_id} پس از بررسی تأیید نشد. "
                    "اگر لازم است، مشخصات را اصلاح و دوباره ثبت کن.",
                )
            except Exception as exc:
                print(f"Could not notify seller for item {item_id}: {exc}")
    else:
        api("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "دستور نامعتبر است.",
        })


def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "Set TELEGRAM_BOT_TOKEN in the hosting service environment variables."
        )

    print("ZarinMah seller bot starting...")
    print(f"Admin ID: {ADMIN_ID}; channel: {CHANNEL_ID}")

    # This process uses long polling. It removes any configured webhook.
    api("deleteWebhook", {"drop_pending_updates": "false"})
    offset = 0

    while True:
        try:
            updates = api(
                "getUpdates",
                {
                    "offset": offset,
                    "timeout": POLL_TIMEOUT,
                    "allowed_updates": json.dumps(
                        ["message", "callback_query"]
                    ),
                },
                timeout=POLL_TIMEOUT + 10,
            )
            for update in updates or []:
                offset = max(offset, int(update["update_id"]) + 1)
                try:
                    if "message" in update:
                        process_message(update["message"])
                    elif "callback_query" in update:
                        process_callback(update["callback_query"])
                except Exception as exc:
                    print(f"Update processing error: {exc}")
        except Exception as exc:
            print(f"Polling error: {exc}")
            time.sleep(5)


if __name__ == "__main__":
    main()
