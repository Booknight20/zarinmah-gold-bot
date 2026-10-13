import os
import sys
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = "@ZarinMahGold"
CHANNEL_USERNAME = "ZarinMahGold"

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def telegram_request(method, payload):
    """Send a request to Telegram Bot API."""
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


def publish_guide(title, text):
    """Publish a guide post and return its message link."""
    result = telegram_request(
        "sendMessage",
        {
            "chat_id": CHANNEL,
            "text": text,
            "disable_web_page_preview": True,
        },
    )

    message_id = result["message_id"]
    link = f"https://t.me/{CHANNEL_USERNAME}/{message_id}"

    print(f"{title}: {link}")
    return link, message_id


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing from GitHub Secrets."
        )

    # Guide 1: prices, news and analysis
    analysis_text = (
        "📊 راهنمای قیمت و تحلیل بازار زرین ماه\n\n"
        "در این بخش، مطالب مربوط به قیمت طلا، سکه، دلار، "
        "اخبار اقتصادی و تحلیل بازار منتشر می‌شود.\n\n"
        "🔎 برای پیدا کردن مطالب این بخش، روی هشتگ زیر بزنید:\n"
        "#قیمت_و_تحلیل\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )

    analysis_link, _ = publish_guide(
        "Price and analysis guide",
        analysis_text,
    )

    # Guide 2: gold items for sale
    products_text = (
        "💍 راهنمای محصولات طلا برای فروش\n\n"
        "در این بخش، آگهی‌های طلا و سکه‌ای که برای فروش "
        "معرفی می‌شوند قرار می‌گیرند.\n\n"
        "🏷️ برای پیدا کردن آگهی‌های این بخش، روی هشتگ زیر بزنید:\n"
        "#محصولات_برای_فروش\n\n"
        "📩 اگر طلایی برای فروش دارید، می‌توانید برای هماهنگی "
        "و انتشار رایگان آگهی با پشتیبانی تماس بگیرید:\n"
        "@ZarinMah_Support\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )

    products_link, _ = publish_guide(
        "Products for sale guide",
        products_text,
    )

    # Main menu
    menu_text = (
        "🌙 زرین ماه | طلای کم‌اجرت\n\n"
        "به ویترین زرین ماه خوش آمدید.\n\n"
        "از منوی زیر، بخش موردنظرتان را انتخاب کنید:"
    )

    menu = telegram_request(
        "sendMessage",
        {
            "chat_id": CHANNEL,
            "text": menu_text,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": "📊 قیمت و تحلیل بازار",
                            "url": analysis_link,
                        }
                    ],
                    [
                        {
                            "text": "💍 محصولات طلا برای فروش",
                            "url": products_link,
                        }
                    ],
                ]
            },
            "disable_web_page_preview": True,
        },
    )

    menu_message_id = menu["message_id"]
    print(
        "Main menu published: "
        f"https://t.me/{CHANNEL_USERNAME}/{menu_message_id}"
    )

    # Try to pin the menu. Failure to pin does not undo publication.
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

    print("Done. All menu posts have been published.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)
