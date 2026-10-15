import os
import sys
import re
import requests
from html.parser import HTMLParser

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = "@ZarinMahGold"
CHANNEL_USERNAME = "ZarinMahGold"

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CHANNEL_URL = f"https://t.me/{CHANNEL_USERNAME}"
PUBLIC_CHANNEL_URL = f"https://t.me/s/{CHANNEL_USERNAME}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ZarinMahBot/1.0)"
}


class TelegramChannelParser(HTMLParser):
    """Extract public channel messages without external HTML libraries."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.div_depth = 0
        self.wrapper_depth = None
        self.text_depth = None
        self.current_message = None
        self.messages = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "div":
            self.div_depth += 1
            classes = attrs.get("class", "").split()

            if (
                "tgme_widget_message_wrap" in classes
                and self.wrapper_depth is None
            ):
                self.wrapper_depth = self.div_depth
                self.current_message = {
                    "text": "",
                    "link": "",
                }

            if (
                self.current_message is not None
                and "tgme_widget_message_text" in classes
            ):
                self.text_depth = self.div_depth

        elif (
            tag == "a"
            and self.current_message is not None
            and "tgme_widget_message_date"
            in attrs.get("class", "").split()
        ):
            self.current_message["link"] = attrs.get("href", "")

    def handle_endtag(self, tag):
        if tag != "div":
            return

        if (
            self.text_depth is not None
            and self.div_depth == self.text_depth
        ):
            self.text_depth = None

        if (
            self.wrapper_depth is not None
            and self.div_depth == self.wrapper_depth
        ):
            if self.current_message is not None:
                self.messages.append(self.current_message)

            self.current_message = None
            self.wrapper_depth = None
            self.text_depth = None

        self.div_depth -= 1

    def handle_data(self, data):
        if (
            self.current_message is not None
            and self.text_depth is not None
        ):
            self.current_message["text"] += data


def get_latest_hourly_price_link():
    """Find the newest public channel post tagged #قیمت_ساعتی."""

    try:
        response = requests.get(
            PUBLIC_CHANNEL_URL,
            headers=HEADERS,
            timeout=25,
        )
        response.raise_for_status()

        parser = TelegramChannelParser()
        parser.feed(response.text)

        matches = []

        for message in parser.messages:
            text = message["text"]
            link = message["link"]

            if "#قیمت_ساعتی" not in text:
                continue

            match = re.search(r"/(\d+)(?:\?.*)?$", link)

            if match:
                message_id = int(match.group(1))
                matches.append((message_id, link))

        if matches:
            message_id, link = max(
                matches,
                key=lambda item: item[0],
            )
            print(
                f"Latest hourly price found: {link} "
                f"(message_id={message_id})"
            )
            return link

        raise RuntimeError(
            "No public channel post tagged #قیمت_ساعتی was found. "
            "Check the hashtag and public channel access."
        )

    except Exception as error:
        print(f"ERROR finding latest hourly price: {error}")
        raise RuntimeError(
            "Could not determine the latest hourly-price link. "
            "Menu publication stopped to avoid an incorrect link."
        ) from error


def telegram_request(method, payload):
    response = requests.post(
        f"{API_URL}/{method}",
        json=payload,
        timeout=30,
    )

    try:
        data = response.json()
    except ValueError as error:
        raise RuntimeError(
            f"Telegram returned an invalid response: "
            f"{response.status_code}"
        ) from error

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
    link = f"{CHANNEL_URL}/{message_id}"

    print(f"{title}: {link}")
    return link, message_id


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing from GitHub Secrets."
        )

    # Find the latest price BEFORE publishing the menu.
    latest_price_link = get_latest_hourly_price_link()

    analysis_text = (
        "📈 راهنمای تحلیل روزانه زرین ماه\n\n"
        "تحلیل‌های روزانه بازار طلا، سکه و دلار در این بخش منتشر می‌شوند.\n\n"
        "برای پیدا کردن تحلیل‌ها، روی هشتگ زیر بزنید:\n"
        "#تحلیل_روزانه\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )
    analysis_link, _ = publish_post(
        "Daily analysis guide",
        analysis_text,
    )

    news_text = (
        "📰 راهنمای اخبار بازار زرین ماه\n\n"
        "خبرهای اثرگذار بر بازار طلا، سکه و ارز در این بخش قرار می‌گیرند.\n\n"
        "برای پیدا کردن خبرها، روی هشتگ زیر بزنید:\n"
        "#اخبار_بازار\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )
    news_link, _ = publish_post(
        "Market news guide",
        news_text,
    )

    products_text = (
        "💍 راهنمای محصولات طلا برای فروش\n\n"
        "در این بخش، آگهی‌های طلا و سکه‌ای که برای فروش معرفی می‌شوند قرار می‌گیرند.\n\n"
        "🏷️ برای پیدا کردن آگهی‌های این بخش، روی هشتگ زیر بزنید:\n"
        "#محصولات_برای_فروش\n\n"
        "📩 اگر طلایی برای فروش دارید، برای هماهنگی و انتشار رایگان آگهی با پشتیبانی تماس بگیرید:\n"
        "@ZarinMah_Support\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )
    products_link, _ = publish_post(
        "Products for sale guide",
        products_text,
    )

    submenu_text = (
        "📊 قیمت و تحلیل بازار زرین ماه\n\n"
        "از دکمه‌های زیر، بخش موردنظرتان را انتخاب کنید.\n\n"
        "💰 قیمت‌های ساعتی: آخرین گزارش قیمت موجود\n"
        "📈 تحلیل روزانه: گزارش‌های تحلیلی\n"
        "📰 اخبار بازار: خبرهای بازار طلا و ارز\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )

    submenu_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "💰 قیمت‌های ساعتی",
                    "url": latest_price_link,
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

    print(
        f"Main menu published: "
        f"{CHANNEL_URL}/{menu_message_id}"
    )

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
            "Menu was published, but could not be pinned: "
            f"{error}"
        )

    print("Done. Main menu and submenu have been published.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)
