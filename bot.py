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
CHANNEL = "@ZarinMahGold"

TEHRAN = ZoneInfo("Asia/Tehran")

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
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}


# =========================================================
# فقط منابع رسمی TGJU
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

    text = html.unescape(str(value))

    text = text.replace("\u200c", " ")
    text = text.replace("\u200f", " ")
    text = text.replace("\ufeff", " ")

    text = text.replace("٬", ",")
    text = text.replace("،", ",")

    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)

    return text.strip()


# =========================================================
# تبدیل عدد ریال/تومان
# =========================================================

def parse_number(value, unit="toman"):
    if not value:
        return None

    text = normalize_digits(
        clean_text(value)
    )

    text = text.replace(",", "")
    text = text.replace(" ", "")

    match = re.search(
        r"\d+(?:\.\d+)?",
        text,
    )

    if not match:
        return None

    try:
        number = float(match.group(0))
    except ValueError:
        return None

    if unit == "rial":
        number /= 10

    return int(round(number))


# =========================================================
# استخراج Message ID از لینک تلگرام
# =========================================================

def get_message_id(link):
    match = re.search(
        r"/(\d+)$",
        link or "",
    )

    if not match:
        return 0

    return int(match.group(1))


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

            if not text_node or not date_node:
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

            if not text or not link:
                continue

            if link in seen_links:
                continue

            seen_links.add(link)

            page_posts.append(
                {
                    "text": text,
                    "link": link,
                    "message_id": get_message_id(
                        link
                    ),
                }
            )

        print(
            "Posts found on page:",
            len(page_posts),
        )

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

        # برای صفحه بعد، از قدیمی‌ترین Message ID
        before = str(min(ids))

    # -----------------------------------------------------
    # مهم:
    # دیگر به ترتیب HTML اعتماد نمی‌کنیم.
    # Message ID را معیار قطعی تازگی قرار می‌دهیم.
    # -----------------------------------------------------

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
# استخراج بخش یک دارایی از داخل پست
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

    # بخش بعدی با عنوان ⭕️ شروع می‌شود
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
# فقط «قیمت لحظه ای»
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

def parse_gold_post(text):

    patterns = [
        r"(?:^|\n)\s*⭕️\s*قیمت\s*طلای\s*(?:18|۱۸)\s*عیار",
        r"(?:^|\n)\s*⭕️\s*طلای\s*(?:18|۱۸)\s*عیار",
        r"(?:^|\n)\s*قیمت\s*طلای\s*(?:18|۱۸)\s*عیار",
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


# =========================================================
# TGJU ارز
# فقط #قیمت_دلار اصلی
# =========================================================

def parse_currency_post(text):

    text = normalize_digits(
        clean_text(text)
    )

    dollar_match = re.search(
        r"#قیمت[_\s]*دلار\b",
        text,
        flags=re.IGNORECASE,
    )

    if not dollar_match:
        return {}

    start = dollar_match.end()

    remaining = text[start:]

    # فقط بخش دلار اصلی.
    # به محض رسیدن به دلار توافقی / هرات / سلیمانیه
    # متوقف می‌شویم.

    stop_patterns = [
        r"#قیمت[_\s]*دلار[_\s]*توافقی",
        r"#قیمت[_\s]*دلار[_\s]*سلیمانیه",
        r"#قیمت[_\s]*دلار[_\s]*هرات",
        r"#قیمت[_\s]*دلار[_\s]*سنا",
        r"#قیمت[_\s]*دلار[_\s]*نیما",
        r"⭕️\s*قیمت\s*دلار\s*دولتی",
    ]

    stop_positions = []

    for pattern in stop_patterns:
        stop = re.search(
            pattern,
            remaining,
            flags=re.IGNORECASE,
        )

        if stop:
            stop_positions.append(
                stop.start()
            )

    if stop_positions:
        section = remaining[
            :min(stop_positions)
        ]
    else:
        section = remaining

    price = extract_instant_price(
        section,
        100_000,
        1_000_000,
    )

    if not price:
        return {}

    return {
        "dollar": price,
    }


# =========================================================
# TGJU سکه
# =========================================================

def parse_coin_post(text):

    text = normalize_digits(
        clean_text(text)
    )

    definitions = {
        "coin": {
            "pattern": (
                r"(?:^|\n)\s*⭕️\s*"
                r"سکه\s*امامی"
            ),
            "min": 100_000_000,
            "max": 5_000_000_000,
        },
        "half": {
            "pattern": (
                r"(?:^|\n)\s*⭕️\s*"
                r"نیم\s*سکه"
            ),
            "min": 50_000_000,
            "max": 2_000_000_000,
        },
        "quarter": {
            "pattern": (
                r"(?:^|\n)\s*⭕️\s*"
                r"ربع\s*سکه"
            ),
            "min": 20_000_000,
            "max": 1_000_000_000,
        },
    }

    result = {}

    for asset, config in definitions.items():

        section = get_asset_section(
            text,
            config["pattern"],
        )

        price = extract_instant_price(
            section,
            config["min"],
            config["max"],
        )

        if price:
            result[asset] = price

    return result


# =========================================================
# پیدا کردن آخرین پست مرتبط با یک دارایی
# =========================================================

def get_latest_asset_price(
    channel_key,
    asset,
):
    config = PRICE_SOURCES[
        channel_key
    ]

    posts = fetch_channel_posts(
        config["channel"]
    )

    if channel_key == "gold":
        parser = parse_gold_post

    elif channel_key == "currency":
        parser = parse_currency_post

    elif channel_key == "coin":
        parser = parse_coin_post

    else:
        raise ValueError(
            f"Unknown channel key: {channel_key}"
        )

    # -----------------------------------------------------
    # از جدیدترین Message ID به قدیمی‌ترین می‌رویم.
    # بنابراین دقیقاً جدیدترین پست مرتبط را می‌گیریم.
    # -----------------------------------------------------

    for post in posts:

        parsed = parser(
            post["text"]
        )

        if asset not in parsed:
            continue

        price = parsed[asset]

        print(
            "LATEST MATCH"
        )

        print(
            "Source:",
            config["name"],
        )

        print(
            "Message ID:",
            post["message_id"],
        )

        print(
            "Message link:",
            post["link"],
        )

        print(
            "Asset:",
            asset,
        )

        print(
            "Instant price:",
            f"{price:,}",
            "rial",
        )

        return {
            "price": price,
            "link": post["link"],
            "message_id": post["message_id"],
        }

    raise RuntimeError(
        f"قیمت لحظه‌ای {asset} "
        f"در کانال {config['channel']} "
        f"پیدا نشد."
    )


# =========================================================
# دریافت آخرین قیمت‌های رسمی
# =========================================================

def get_official_prices():

    result = {}

    # -----------------------------------------------------
    # طلای ۱۸ عیار
    # -----------------------------------------------------

    gold = get_latest_asset_price(
        "gold",
        "gold18",
    )

    result["gold18"] = gold["price"]

    # -----------------------------------------------------
    # دلار
    # -----------------------------------------------------

    dollar = get_latest_asset_price(
        "currency",
        "dollar",
    )

    result["dollar"] = dollar["price"]

    # -----------------------------------------------------
    # سکه امامی
    # -----------------------------------------------------

    coin = get_latest_asset_price(
        "coin",
        "coin",
    )

    result["coin"] = coin["price"]

    # -----------------------------------------------------
    # نیم سکه
    # -----------------------------------------------------

    half = get_latest_asset_price(
        "coin",
        "half",
    )

    result["half"] = half["price"]

    # -----------------------------------------------------
    # ربع سکه
    # -----------------------------------------------------

    quarter = get_latest_asset_price(
        "coin",
        "quarter",
    )

    result["quarter"] = quarter["price"]

    print()
    print(
        "================================"
    )

    print(
        "LATEST OFFICIAL TGJU "
        "INSTANT PRICES"
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    return result


# =========================================================
# قیمت‌های قبلی
# =========================================================

def load_previous_prices():

    if not os.path.exists(
        PREVIOUS_FILE
    ):
        return None

    try:
        with open(
            PREVIOUS_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except Exception as error:

        print(
            "Could not load previous prices:",
            error,
        )

        return None


def save_current_prices(
    prices,
):
    with open(
        PREVIOUS_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            prices,
            file,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# وضعیت ارسال
# =========================================================

def load_send_status():

    if not os.path.exists(
        STATUS_FILE
    ):
        return {}

    try:
        with open(
            STATUS_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except Exception as error:

        print(
            "Could not load send status:",
            error,
        )

        return {}


def save_hourly_send_status(
    slot,
):
    status = load_send_status()

    status["hourly"] = {
        "slot": slot,
        "sent_at": datetime.now(
            TEHRAN
        ).isoformat(),
    }

    with open(
        STATUS_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            status,
            file,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# تغییر قیمت
# =========================================================

def change_text(
    current,
    previous,
):
    if previous is None:
        return "🆕 اولین ثبت"

    difference = (
        current - previous
    )

    if difference > 0:
        return (
            f"🟢 ▲ +{difference:,} تومان"
        )

    if difference < 0:
        return (
            f"🔴 ▼ {difference:,} تومان"
        )

    return (
        "⚪ ➖ بدون تغییر"
    )


# =========================================================
# ساخت پیام
# =========================================================

def build_message(
    prices,
    previous,
):
    previous = previous or {}

    update_time = datetime.now(
        TEHRAN
    ).strftime(
        "%H:%M"
    )

    return f"""🌙✨ زرین ماه
💎 آخرین قیمت لحظه‌ای رسمی TGJU

━━━━━━━━━━━━━━━━━━

🟡 طلای ۱۸ عیار
💰 {prices["gold18"]:,} تومان
{change_text(
    prices["gold18"],
    previous.get("gold18"),
)}

🪙 سکه امامی
💰 {prices["coin"]:,} تومان
{change_text(
    prices["coin"],
    previous.get("coin"),
)}

🪙 نیم‌سکه
💰 {prices["half"]:,} تومان
{change_text(
    prices["half"],
    previous.get("half"),
)}

🪙 ربع‌سکه
💰 {prices["quarter"]:,} تومان
{change_text(
    prices["quarter"],
    previous.get("quarter"),
)}

💵 دلار آزاد
💰 {prices["dollar"]:,} تومان
{change_text(
    prices["dollar"],
    previous.get("dollar"),
)}

━━━━━━━━━━━━━━━━━━

🕒 آخرین بروزرسانی: {update_time}

📊 منبع رسمی: TGJU

🔸 طلا: https://t.me/tgjugold
🔸 سکه: https://t.me/tgjucoin
🔸 ارز: https://t.me/tgjucurrency

━━━━━━━━━━━━━━━━━━

🌙 زرین ماه
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""


# =========================================================
# ارسال تلگرام
# =========================================================

def send_to_telegram(
    message,
):
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN "
            "تنظیم نشده است."
        )

    url = (
        "https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": CHANNEL,
            "text": message,
        },
        timeout=30,
    )

    print(
        "Telegram HTTP status:",
        response.status_code,
    )

    print(
        "Telegram response:",
        response.text,
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result}"
        )


# =========================================================
# اجرای اصلی
# =========================================================

def main():

    print(
        "================================="
    )

    print(
        "Starting ZarinMah "
        "TGJU instant price bot..."
    )

    print(
        "================================="
    )

    scheduled_run = (
        os.environ.get(
            "SCHEDULED_RUN"
        )
        == "true"
    )

    watchdog_retry = (
        os.environ.get(
            "WATCHDOG_RETRY"
        )
        == "true"
    )

    now = datetime.now(
        TEHRAN
    )

    print(
        "Tehran hour:",
        now.hour,
    )

    current_slot = (
        now.strftime(
            "%Y-%m-%d %H"
        )
    )

    # -----------------------------------------------------
    # خاموشی 22:00 تا 08:59
    # -----------------------------------------------------

    if (
        scheduled_run
        or watchdog_retry
    ):

        if (
            now.hour >= 22
            or now.hour < 9
        ):

            print(
                "Price bot is disabled "
                "between 22:00 and 08:59 Tehran time."
            )

            return

    # -----------------------------------------------------
    # جلوگیری از ارسال تکراری
    # -----------------------------------------------------

    if (
        scheduled_run
        or watchdog_retry
    ):

        status = (
            load_send_status()
        )

        last_slot = (
            status
            .get(
                "hourly",
                {},
            )
            .get(
                "slot"
            )
        )

        if (
            last_slot
            == current_slot
        ):

            print(
                f"Hourly post for "
                f"{current_slot} "
                "has already been sent."
            )

            print(
                "Skipping duplicate message."
            )

            return

    # -----------------------------------------------------
    # قیمت قبلی
    # -----------------------------------------------------

    previous = (
        load_previous_prices()
    )

    # -----------------------------------------------------
    # دریافت آخرین قیمت لحظه‌ای TGJU
    # -----------------------------------------------------

    prices = (
        get_official_prices()
    )

    # -----------------------------------------------------
    # ساخت پیام
    # -----------------------------------------------------

    message = build_message(
        prices,
        previous,
    )

    # -----------------------------------------------------
    # ارسال
    # -----------------------------------------------------

    print(
        "Sending message to Telegram..."
    )

    send_to_telegram(
        message
    )

    print(
        "Telegram message sent successfully."
    )

    # -----------------------------------------------------
    # ذخیره وضعیت
    # -----------------------------------------------------

    if (
        scheduled_run
        or watchdog_retry
    ):

        save_hourly_send_status(
            current_slot
        )

        print(
            "Hourly send status saved."
        )

    # -----------------------------------------------------
    # ذخیره قیمت
    # -----------------------------------------------------

    save_current_prices(
        prices
    )

    print(
        "Verified prices saved."
    )

    print(
        "Bot completed successfully."
    )


# =========================================================
# اجرا
# =========================================================

if __name__ == "__main__":
    main()
