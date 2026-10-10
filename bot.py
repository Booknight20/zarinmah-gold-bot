import os
import re
import json
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# =========================================================
# تنظیمات
# =========================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

EITAAYAR_TOKEN = os.environ.get(
    "EITAAYAR_TOKEN",
)

EITAA_CHAT_ID = os.environ.get(
    "EITAA_CHAT_ID",
)

CHANNEL = "@ZarinMahGold"

TEHRAN = ZoneInfo(
    "Asia/Tehran"
)

PREVIOUS_FILE = "previous_prices.json"
STATUS_FILE = "send_status.json"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": (
        "fa-IR,fa;q=0.9,en;q=0.8"
    ),
}


# =========================================================
# منابع رسمی TGJU
# =========================================================

PRICE_SOURCES = {
    "gold": {
        "name": "TGJU طلا",
        "channel": "tgjugold",
    },
    "currency": {
        "name": "TGJU ارز",
        "channel": "tgjucurrency",
    },
    "coin": {
        "name": "TGJU سکه",
        "channel": "tgjucoin",
    },
}

# منبع جایگزین برای روزهای تعطیل یا نبود قیمت تازه در TGJU
NAVASAN_CHANNEL = "navasanchannel"
MAX_TGJU_AGE_MINUTES = 360
MAX_NAVASAN_AGE_MINUTES = 360

# برای نمایش شفاف منبع هر دارایی در پیام ارسالی
PRICE_METADATA = {}


# =========================================================
# تبدیل اعداد فارسی و عربی
# =========================================================

def normalize_digits(value):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )

    return str(value).translate(table)


# =========================================================
# پاکسازی متن
# =========================================================

def clean_text(value):
    if not value:
        return ""

    text = html.unescape(
        str(value)
    )

    text = text.replace(
        "\u200c",
        " ",
    )

    text = text.replace(
        "\u200f",
        " ",
    )

    text = text.replace(
        "\ufeff",
        " ",
    )

    text = text.replace(
        "٬",
        ",",
    )

    text = text.replace(
        "،",
        ",",
    )

    text = re.sub(
        r"\r\n?",
        "\n",
        text,
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n+",
        "\n",
        text,
    )

    return text.strip()


# =========================================================
# تبدیل عدد
# =========================================================

def parse_number(
    value,
    unit="toman",
):
    if not value:
        return None

    text = normalize_digits(
        clean_text(value)
    )

    text = text.replace(
        ",",
        "",
    )

    text = text.replace(
        " ",
        "",
    )

    match = re.search(
        r"\d+(?:\.\d+)?",
        text,
    )

    if not match:
        return None

    try:
        number = float(
            match.group(0)
        )

    except ValueError:
        return None

    if unit == "rial":
        number /= 10

    return int(
        round(number)
    )


# =========================================================
# استخراج Message ID
# =========================================================

def get_message_id(link):
    match = re.search(
        r"/(\d+)$",
        link or "",
    )

    if not match:
        return 0

    return int(
        match.group(1)
    )


# =========================================================
# دریافت پست‌های کانال
# =========================================================

def fetch_channel_posts(
    channel,
    max_pages=8,
):
    posts = []
    seen_links = set()
    before = None

    for page_number in range(
        1,
        max_pages + 1,
    ):

        url = (
            f"https://t.me/s/{channel}"
        )

        if before:
            url += (
                f"?before={before}"
            )

        print(
            f"Reading {channel} "
            f"page {page_number}..."
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        wrappers = soup.select(
            "div.tgme_widget_message_wrap"
        )

        if not wrappers:
            break

        page_posts = []

        for wrapper in wrappers:

            text_node = wrapper.select_one(
                "div.tgme_widget_message_text"
            )

            date_node = wrapper.select_one(
                "a.tgme_widget_message_date"
            )

            if (
                not text_node
                or not date_node
            ):
                continue

            text = clean_text(
                text_node.get_text(
                    "\n",
                    strip=True,
                )
            )

            link = date_node.get(
                "href",
                "",
            )

            if not text:
                continue

            if not link:
                continue

            if link in seen_links:
                continue

            seen_links.add(
                link
            )

            time_node = date_node.select_one("time")
            posted_at = None

            if time_node:
                posted_at = time_node.get("datetime")

            if not posted_at:
                posted_at = date_node.get("datetime")

            page_posts.append(
                {
                    "text": text,
                    "link": link,
                    "message_id": get_message_id(
                        link
                    ),
                    "posted_at": posted_at,
                }
            )

        print(
            "Posts found on page:",
            len(page_posts),
        )

        if not page_posts:
            break

        posts.extend(
            page_posts
        )

        ids = [
            post["message_id"]
            for post in page_posts
            if post["message_id"] > 0
        ]

        if not ids:
            break

        before = str(
            min(ids)
        )

    posts.sort(
        key=lambda item: item["message_id"],
        reverse=True,
    )

    print(
        f"Total posts collected from "
        f"{channel}: {len(posts)}"
    )

    if posts:
        print(
            "Newest message ID:",
            posts[0]["message_id"],
        )

        print(
            "Newest message link:",
            posts[0]["link"],
        )

    return posts


# =========================================================
# استخراج بخش دارایی
# =========================================================

def get_asset_section(
    text,
    asset_pattern,
):
    text = normalize_digits(
        clean_text(text)
    )

    match = re.search(
        asset_pattern,
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    start = match.end()

    remaining = text[start:]

    next_section = re.search(
        r"(?:^|\n)\s*⭕️",
        remaining,
    )

    if next_section:
        return remaining[
            :next_section.start()
        ]

    return remaining


# =========================================================
# فقط قیمت لحظه‌ای
# =========================================================

def extract_instant_price(
    section,
    minimum,
    maximum,
):
    if not section:
        return None

    match = re.search(
        r"قیمت\s*لحظه\s*ای"
        r"\s*[:：]?\s*"
        r"([\d,]+)"
        r"\s*ریال",
        section,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    price = parse_number(
        match.group(1),
        "rial",
    )

    if not price:
        return None

    if not (
        minimum <= price <= maximum
    ):
        return None

    return price


# =========================================================
# TGJU طلا
# =========================================================

def parse_gold_post(
    text,
):
    patterns = [
        (
            r"(?:^|\n)\s*⭕️\s*"
            r"قیمت\s*طلای\s*(?:18|۱۸)\s*عیار"
        ),
        (
            r"(?:^|\n)\s*⭕️\s*"
            r"طلای\s*(?:18|۱۸)\s*عیار"
        ),
        (
            r"(?:^|\n)\s*"
            r"قیمت\s*طلای\s*(?:18|۱۸)\s*عیار"
        ),
    ]

    for pattern in patterns:

        section = get_asset_section(
            text,
            pattern,
        )

        price = extract_instant_price(
            section,
            100_000,
            500_000_000,
        )

        if price:
            return {
                "gold18": price,
            }

    return {}
