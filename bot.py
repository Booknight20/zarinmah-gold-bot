import os
import re
import json
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

# ========================= تنظیمات =========================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
EITAAYAR_TOKEN = os.environ.get("EITAAYAR_TOKEN")
EITAA_CHAT_ID = os.environ.get("EITAA_CHAT_ID")

CHANNEL = "@ZarinMahGold"
TEHRAN = ZoneInfo("Asia/Tehran")

PREVIOUS_FILE = "previous_prices.json"
STATUS_FILE = "send_status.json"

NAVASAN_CHANNEL = "navasanchannel"

# حداکثر سن قابل‌قبول قیمت‌ها: ۶ ساعت
MAX_TGJU_AGE_MINUTES = 360
MAX_NAVASAN_AGE_MINUTES = 360

PRICE_METADATA = {}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}

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

ASSETS = (
    "gold18",
    "dollar",
    "coin",
    "half",
    "quarter",
)


# ========================= ابزارهای عمومی =========================

def normalize_digits(value):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )
    return str(value).translate(table)


def clean_text(value):
    if not value:
        return ""

    text = html.unescape(str(value))

    for char in ("\u200c", "\u200f", "\ufeff"):
        text = text.replace(char, " ")

    text = text.replace("٬", ",").replace("،", ",")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)

    return text.strip()


def parse_number(value, unit="toman"):
    if not value:
        return None

    text = normalize_digits(clean_text(value))
    text = text.replace(",", "").replace(" ", "")

    match = re.search(r"\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        number = float(match.group(0))
    except ValueError:
        return None

    if unit == "rial":
        number /= 10

    return int(round(number))


def get_message_id(link):
    match = re.search(r"/(\d+)$", link or "")
    return int(match.group(1)) if match else 0


# ========================= دریافت پست‌های تلگرام =========================

def fetch_channel_posts(channel, max_pages=8):
    posts = []
    seen_links = set()
    before = None

    for page_number in range(1, max_pages + 1):
        url = f"https://t.me/s/{channel}"

        if before:
            url += f"?before={before}"

        print(f"Reading {channel} page {page_number}...")

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        wrappers = soup.select("div.tgme_widget_message_wrap")

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

            if not text_node or not date_node:
                continue

            text = clean_text(
                text_node.get_text("\n", strip=True)
            )
            link = date_node.get("href", "")

            if not text or not link or link in seen_links:
                continue

            seen_links.add(link)

            time_node = date_node.select_one("time")
            posted_at = (
                time_node.get("datetime")
                if time_node
                else date_node.get("datetime")
            )

            page_posts.append({
                "text": text,
                "link": link,
                "message_id": get_message_id(link),
                "posted_at": posted_at,
            })

        print("Posts found on page:", len(page_posts))

        if not page_posts:
            break

        posts.extend(page_posts)

        ids = [
            post["message_id"]
            for post in page_posts
            if post["message_id"] > 0
        ]

        if not ids:
            break

        before = str(min(ids))

    posts.sort(
        key=lambda item: item["message_id"],
        reverse=True,
    )

    print(
        f"Total posts collected from {channel}: {len(posts)}"
    )

    if posts:
        print("Newest message link:", posts[0]["link"])

    return posts


# ========================= استخراج قیمت از TGJU =========================

def get_asset_section(text, asset_pattern):
    text = normalize_digits(clean_text(text))

    match = re.search(
        asset_pattern,
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    remaining = text[match.end():]

    next_section = re.search(
        r"(?:^|\n)\s*⭕️",
        remaining,
    )

    return (
        remaining[:next_section.start()]
        if next_section
        else remaining
    )


def extract_instant_price(section, minimum, maximum):
    if not section:
        return None

    match = re.search(
        r"قیمت\s*لحظه\s*ای\s*[:：]?\s*([\d,]+)\s*ریال",
        section,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    price = parse_number(match.group(1), "rial")

    if price and minimum <= price <= maximum:
        return price

    return None


def parse_gold_post(text):
    patterns = (
        r"(?:^|\n)\s*⭕️\s*قیمت\s*طلای\s*(?:18|۱۸)\s*عیار",
        r"(?:^|\n)\s*⭕️\s*طلای\s*(?:18|۱۸)\s*عیار",
        r"(?:^|\n)\s*قیمت\s*طلای\s*(?:18|۱۸)\s*عیار",
    )

    for pattern in patterns:
        price = extract_instant_price(
            get_asset_section(text, pattern),
            100_000,
            500_000_000,
        )

        if price:
            return {"gold18": price}

    return {}


def parse_currency_post(text):
    text = normalize_digits(clean_text(text))

    match = re.search(
        r"#قیمت[_\s]*دلار\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return {}

    remaining = text[match.end():]

    stop_patterns = (
        r"#قیمت[_\s]*دلار[_\s]*توافقی",
        r"#قیمت[_\s]*دلار[_\s]*سلیمانیه",
        r"#قیمت[_\s]*دلار[_\s]*هرات",
        r"#قیمت[_\s]*دلار[_\s]*سنا",
        r"#قیمت[_\s]*دلار[_\s]*نیما",
        r"⭕️\s*قیمت\s*دلار\s*دولتی",
    )

    positions = []

    for pattern in stop_patterns:
        stop = re.search(
            pattern,
            remaining,
            flags=re.IGNORECASE,
        )
        if stop:
            positions.append(stop.start())

    section = (
        remaining[:min(positions)]
        if positions
        else remaining
    )

    price = extract_instant_price(
        section,
        100_000,
        1_000_000,
    )

    return {"dollar": price} if price else {}


def parse_coin_post(text):
    definitions = {
        "coin": (
            r"(?:^|\n)\s*⭕️\s*سکه\s*امامی",
            100_000_000,
            5_000_000_000,
        ),
        "half": (
            r"(?:^|\n)\s*⭕️\s*نیم\s*سکه",
            50_000_000,
            2_000_000_000,
        ),
        "quarter": (
            r"(?:^|\n)\s*⭕️\s*ربع\s*سکه",
            20_000_000,
            1_000_000_000,
        ),
    }

    result = {}

    for asset, (pattern, minimum, maximum) in definitions.items():
        price = extract_instant_price(
            get_asset_section(text, pattern),
            minimum,
            maximum,
        )

        if price:
            result[asset] = price

    return result


# ========================= کنترل تازگی قیمت =========================

def parse_post_datetime(value):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=TEHRAN)

        return parsed.astimezone(TEHRAN)

    except (ValueError, TypeError):
        return None


def post_age_minutes(post):
    posted_at = parse_post_datetime(post.get("posted_at"))

    if not posted_at:
        return None

    return (
        datetime.now(TEHRAN) - posted_at
    ).total_seconds() / 60


def is_post_fresh(post, max_age_minutes):
    age = post_age_minutes(post)

    return (
        age is not None
        and -10 <= age <= max_age_minutes
    )


def get_latest_asset_price(
    channel_key,
    asset,
    require_fresh=False,
):
    config = PRICE_SOURCES[channel_key]
    posts = fetch_channel_posts(config["channel"])

    parser = {
        "gold": parse_gold_post,
        "currency": parse_currency_post,
        "coin": parse_coin_post,
    }[channel_key]

    for post in posts:
        parsed = parser(post["text"])

        if asset not in parsed:
            continue

        if require_fresh and not is_post_fresh(
            post,
            MAX_TGJU_AGE_MINUTES,
        ):
            print(
                f"TGJU price for {asset} is stale "
                f"or timestamp is missing: {post.get('link')}"
            )

            raise RuntimeError(
                f"قیمت تازه برای {asset} در TGJU موجود نیست."
            )

        price = parsed[asset]

        print(
            "LATEST TGJU MATCH:",
            config["name"],
            asset,
            f"{price:,}",
            post.get("link"),
        )

        return {
            "price": price,
            "link": post["link"],
            "message_id": post["message_id"],
            "posted_at": post.get("posted_at"),
        }

    raise RuntimeError(
        f"قیمت لحظه‌ای {asset} در کانال "
        f"{config['channel']} پیدا نشد."
    )


# ========================= منبع جایگزین نوسان =========================

def extract_navasan_line_price(line):
    line = normalize_digits(clean_text(line))

    match = re.search
