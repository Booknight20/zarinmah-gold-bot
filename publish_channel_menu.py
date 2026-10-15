import os
import sys
import re
import json
import requests
from html.parser import HTMLParser
from pathlib import Path

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = "@ZarinMahGold"
CHANNEL_USERNAME = "ZarinMahGold"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CHANNEL_URL = f"https://t.me/{CHANNEL_USERNAME}"
PUBLIC_CHANNEL_URL = f"https://t.me/s/{CHANNEL_USERNAME}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ZarinMahBot/1.0)"}
ARCHIVE_STATE_FILE = Path("channel_archive_state.json")


class TelegramChannelParser(HTMLParser):
    """Parse public channel HTML without third-party dependencies."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.wrapper_depth = None
        self.text_depth = None
        self.current = None
        self.messages = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            self.depth += 1
            classes = attrs.get("class", "").split()
            if "tgme_widget_message_wrap" in classes and self.wrapper_depth is None:
                self.wrapper_depth = self.depth
                self.current = {"text": "", "link": ""}
            if self.current is not None and "tgme_widget_message_text" in classes:
                self.text_depth = self.depth
        elif tag == "a" and self.current is not None:
            if "tgme_widget_message_date" in attrs.get("class", "").split():
                self.current["link"] = attrs.get("href", "")

    def handle_endtag(self, tag):
        if tag != "div":
            return
        if self.text_depth == self.depth:
            self.text_depth = None
        if self.wrapper_depth == self.depth:
            if self.current is not None:
                self.messages.append(self.current)
            self.current = None
            self.wrapper_depth = None
            self.text_depth = None
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        if self.current is not None and self.text_depth is not None:
            self.current["text"] += data


def get_latest_hourly_price_link():
    try:
        response = requests.get(PUBLIC_CHANNEL_URL, headers=HEADERS, timeout=25)
        response.raise_for_status()
        parser = TelegramChannelParser()
        parser.feed(response.text)
        matches = []
        for message in parser.messages:
            if "#قیمت_ساعتی" not in message["text"]:
                continue
            match = re.search(r"/(\d+)(?:\?.*)?$", message["link"])
            if match:
                matches.append((int(match.group(1)), message["link"]))
        if matches:
            message_id, link = max(matches, key=lambda item: item[0])
            print(f"Latest hourly price found: {link} (message_id={message_id})")
            return link

        # Do not block menu publication when the public HTML page does not
        # expose the hashtagged post. bot.py updates this button after the
        # next successful hourly price post.
        print(
            "WARNING: No public post tagged #قیمت_ساعتی was detected. "
            "The button will temporarily open the channel; bot.py should "
            "replace it with the exact latest-price link after the next send."
        )
        return CHANNEL_URL
    except Exception as error:
        # Network/HTML parsing errors should not prevent menu publication.
        print(
            "WARNING: Could not find latest hourly-price link: "
            f"{error}. Temporarily linking the button to the channel."
        )
        return CHANNEL_URL


def telegram_request(method, payload):
    response = requests.post(f"{API_URL}/{method}", json=payload, timeout=30)
    try:
        data = response.json()
    except ValueError as error:
        raise RuntimeError(
            f"Telegram returned an invalid response: {response.status_code}"
        ) from error
    if not response.ok or not data.get("ok"):
        raise RuntimeError(
            f"Telegram API error in {method}: {data.get('description', response.text)}"
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


def get_archive_links():
    if not ARCHIVE_STATE_FILE.exists():
        raise RuntimeError(
            "Archive state is missing. Run the ZarinMah News Collector workflow "
            "once after adding channel_archive.py, then run this menu workflow again."
        )
    with ARCHIVE_STATE_FILE.open("r", encoding="utf-8") as file:
        state = json.load(file)
    links = {}
    for key in ("news", "analysis"):
        ids = state.get(key, {}).get("message_ids", [])
        if not ids:
            raise RuntimeError(
                f"No archive page found for {key}. Run the News Collector workflow first."
            )
        links[key] = f"{CHANNEL_URL}/{ids[0]}"
    return links


def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing from GitHub Secrets.")

    latest_price_link = get_latest_hourly_price_link()
    archive_links = get_archive_links()

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

    submenu_text = (
        "📊 قیمت و تحلیل بازار زرین ماه\n\n"
        "از دکمه‌های زیر، بخش موردنظرتان را انتخاب کنید.\n\n"
        "💰 قیمت‌های ساعتی: آخرین گزارش قیمت\n"
        "📈 تحلیل روزانه: آرشیو تحلیل‌ها، جدیدترین در ابتدا\n"
        "📰 اخبار بازار: آرشیو خبرها، جدیدترین در ابتدا\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )
    submenu_markup = {
        "inline_keyboard": [
            [{"text": "💰 قیمت‌های ساعتی", "url": latest_price_link}],
            [{"text": "📈 تحلیل روزانه", "url": archive_links["analysis"]}],
            [{"text": "📰 اخبار بازار", "url": archive_links["news"]}],
        ]
    }
    submenu_link, _ = publish_post(
        "Price and analysis submenu", submenu_text, submenu_markup
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
    menu = telegram_request("sendMessage", {
        "chat_id": CHANNEL,
        "text": menu_text,
        "reply_markup": menu_markup,
        "disable_web_page_preview": True,
    })
    menu_message_id = menu["message_id"]
    print(f"Main menu published: {CHANNEL_URL}/{menu_message_id}")

    try:
        telegram_request("pinChatMessage", {
            "chat_id": CHANNEL,
            "message_id": menu_message_id,
            "disable_notification": True,
        })
        print("Main menu pinned successfully.")
    except Exception as error:
        print(f"Menu was published, but could not be pinned: {error}")

    print("Done. Menu now links to the news and analysis archives.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)
