import os
import sys
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = "@ZarinMahGold"
CHANNEL_USERNAME = "ZarinMahGold"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CHANNEL_URL = f"https://t.me/{CHANNEL_USERNAME}"


def telegram_request(method, payload):
    response = requests.post(
        f"{API_URL}/{method}",
        json=payload,
        timeout=30,
    )
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(
            f"Telegram returned an invalid response: {response.status_code}"
        )
    if not response.ok or not data.get("ok"):
        raise RuntimeError(
            f"Telegram API error in {method}: "
            f"{data.get('description', response.text)}"
        )
    return data["result"]


def publish_post(title, text, reply_markup=None):
    payload = {
        "chat_id": CHANNEL,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    result = telegram_request("sendMessage", payload)
    message_id = result["message_id"]
    link = f"https://t.me/{CHANNEL_USERNAME}/{message_id}"
    print(f"{title}: {link}")
    return link, message_id


def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing from GitHub Secrets.")

    # These guide posts make each section easy to recognize and keep its hashtag visible.
    analysis_text = (
        "📈 راهنمای تحلیل روزانه زرین ماه\n\n"
        "تحلیل‌های روزانه بازار طلا، سکه و دلار در این بخش منتشر می‌شوند.\n\n"
        "برای پیدا کردن تحلیل‌ها، روی هشتگ زیر بزنید:\n"
        "#تحلیل_روزانه\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )
    analysis_link, _ = publish_post("Daily analysis guide", analysis_text)

    news_text = (
        "📰 راهنمای اخبار بازار زرین ماه\n\n"
        "خبرهای اثرگذار بر بازار طلا، سکه و ارز در این بخش قرار می‌گیرند.\n\n"
        "برای پیدا کردن خبرها، روی هشتگ زیر بزنید:\n"
        "#اخبار_بازار\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )
    news_link, _ = publish_post("Market news guide", news_text)

    products_text = (
        "💍 راهنمای محصولات طلا برای فروش\n\n"
        "در این بخش، آگهی‌های طلا و سکه‌ای که برای فروش معرفی می‌شوند قرار می‌گیرند.\n\n"
        "🏷️ برای پیدا کردن آگهی‌های این بخش، روی هشتگ زیر بزنید:\n"
        "#محصولات_برای_فروش\n\n"
        "📩 اگر طلایی برای فروش دارید، برای هماهنگی و انتشار رایگان آگهی با پشتیبانی تماس بگیرید:\n"
        "@ZarinMah_Support\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )
    products_link, _ = publish_post("Products for sale guide", products_text)

    # The hourly bot replaces this URL with the newest hourly-price post after each successful send.
    submenu_text = (
        "📊 قیمت و تحلیل بازار زرین ماه\n\n"
        "از دکمه‌های زیر، بخش موردنظرتان را انتخاب کنید.\n\n"
        "💰 دکمه قیمت‌های ساعتی همیشه به آخرین گزارش قیمت وصل می‌شود.\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )
    submenu_markup = {
        "inline_keyboard": [
            [{"text": "💰 قیمت‌های ساعتی", "url": CHANNEL_URL}],
            [{"text": "📈 تحلیل روزانه", "url": analysis_link}],
            [{"text": "📰 اخبار بازار", "url": news_link}],
        ]
    }
    submenu_link, _ = publish_post(
        "Price and analysis submenu",
        submenu_text,
        submenu_markup,
    )

    menu_text = (
        "🌙 زرین ماه | طلای کم‌اجرت\n\n"
        "به ویترین زرین ماه خوش آمدید.\n\n"
        "از منوی زیر، بخش موردنظرتان را انتخاب کنید:"
    )
    menu_markup = {
        "inline_keyboard": [
            [{"text": "📊 قیمت و تحلیل بازار", "url": submenu_link}],
            [{"text": "💍 محصولات طلا برای فروش", "url": products_link}],
        ]
    }
    menu = telegram_request(
        "sendMessage",
        {
            "chat_id": CHANNEL,
            "text": menu_text,
            "reply_markup": menu_markup,
            "disable_web_page_preview": True,
        },
    )

    menu_message_id = menu["message_id"]
    print(f"Main menu published: https://t.me/{CHANNEL_USERNAME}/{menu_message_id}")

    try:
        telegram_request(
            "pinChatMessage",
            {
                "chat_id": CHANNEL,
                "message_id": menu_message_id,
                "disable_notification": True,
            },
        )
        print("Main menu pinned successfully.")
    except Exception as error:
        print(f"Menu was published, but could not be pinned: {error}")

    print("Done. Main menu and submenu have been published.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)
