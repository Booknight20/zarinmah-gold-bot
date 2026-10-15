import os
import sys
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
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
            f"Telegram returned invalid response: "
            f"{response.status_code}"
        )

    if not response.ok or not data.get("ok"):
        raise RuntimeError(
            f"Telegram API error in {method}: "
            f"{data.get('description', response.text)}"
        )

    return data["result"]


def publish_guide(title, text):
    """Publish a guide post and return its link."""
    result = telegram_request(
        "sendMessage",
        {
            "chat_id": CHANNEL,
            "text": text,
            "disable_web_page_preview": True,
        },
    )

    message_id = result["message_id"]
    link = (
        f"https://t.me/{CHANNEL_USERNAME}/{message_id}"
    )

    print(f"{title}: {link}")
    return link, message_id


def publish_submenu(prices_link, analysis_link, news_link):
    """Publish the three-button market submenu."""
    submenu_text = (
        "📊 قیمت و تحلیل بازار زرین ماه\n\n"
        "لطفاً بخش موردنظر خود را انتخاب کنید:"
    )

    result = telegram_request(
        "sendMessage",
        {
            "chat_id": CHANNEL,
            "text": submenu_text,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": "💰 قیمت‌های ساعتی",
                            "url": prices_link,
                        }
                    ],
                    [
                        {
                            "text": "📈 تحلیل روزانه",
                            "url": analysis_link,
                        }
                    ],
                    [
                        {
                            "text": "📰 اخبار بازار",
                            "url": news_link,
                        }
                    ],
                ]
            },
            "disable_web_page_preview": True,
        },
    )

    message_id = result["message_id"]
    submenu_link = (
        f"https://t.me/{CHANNEL_USERNAME}/{message_id}"
    )

    print(f"Market submenu: {submenu_link}")
    return submenu_link, message_id


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing from GitHub Secrets."
        )

    # 1. Hourly prices guide
    prices_text = (
        "💰 راهنمای قیمت‌های ساعتی زرین ماه\n\n"
        "برای مشاهده قیمت‌های ساعتی طلا، سکه و دلار "
        "از هشتگ زیر استفاده کنید:\n\n"
        "#قیمت_ساعتی\n\n"
        "🌙 زرین ماه | طلای کم‌اجرت"
    )

    prices_link, _ = publish_guide(
        "Hourly prices guide",
        prices_text,
    )

    # 2. Daily analysis guide
    analysis_text = (
        "📈 راهنمای تحلیل روزانه زرین ماه\n\n"
        "تحلیل روزانه بازار طلا، سکه و دلار را "
        "از طریق هشتگ زیر دنبال کنید:\n\n"
        "#تحلیل_روزانه\n\n"
        "🌙 زرین ماه | طلای کم‌اجرت"
    )

    analysis_link, _ = publish_guide(
        "Daily analysis guide",
        analysis_text,
    )

    # 3. Market news guide
    news_text = (
        "📰 راهنمای اخبار بازار زرین ماه\n\n"
        "برای مشاهده خبرهای اقتصادی و اخبار مرتبط "
        "با بازار طلا، سکه و دلار از هشتگ زیر استفاده کنید:\n\n"
        "#اخبار_بازار\n\n"
        "🌙 زرین ماه | طلای کم‌اجرت"
    )

    news_link, _ = publish_guide(
        "Market news guide",
        news_text,
    )

    # 4. Products for sale guide
    products_text = (
        "💍 راهنمای محصولات طلا برای فروش\n\n"
        "در این بخش، آگهی‌های طلا و سکه برای فروش "
        "منتشر می‌شوند.\n\n"
        "🏷️ هشتگ آگهی‌ها:\n"
        "#محصولات_برای_فروش\n\n"
        "📩 اگر طلایی برای فروش دارید، می‌توانید "
        "برای هماهنگی و انتشار رایگان آگهی با پشتیبانی تماس بگیرید:\n"
        "@ZarinMah_Support\n\n"
        "🌙 زرین ماه | طلای کم‌اجرت"
    )

    products_link, _ = publish_guide(
        "Products for sale guide",
        products_text,
    )

    # 5. Publish submenu with three separate buttons
    submenu_link, _ = publish_submenu(
        prices_link,
        analysis_link,
        news_link,
    )

    # 6. Publish the main menu
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
                            "url": submenu_link,
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
    menu_link = (
        f"https://t.me/{CHANNEL_USERNAME}/{menu_message_id}"
    )

    print(f"Main menu: {menu_link}")

    # 7. Pin the new main menu
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
        print(
            "Menu published, but pinning failed:",
            error,
        )

    print("All guides, submenu and main menu published.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)
