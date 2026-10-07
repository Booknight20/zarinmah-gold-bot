import os
import re
import json
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# =========================================================
# تنظیمات اصلی
# =========================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL = "@ZarinMahGold"

TEHRAN = ZoneInfo("Asia/Tehran")

PREVIOUS_FILE = "previous_prices.json"
STATUS_FILE = "send_status.json"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
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
# تبدیل عدد
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
        number = float(
            match.group(0)
        )
    except ValueError:
        return None

    if unit == "rial":
        number /= 10

    return int(round(number))


# =========================================================
# دریافت پست‌های کانال
# =========================================================

def fetch_channel_posts(
    channel,
    max_pages=5,
):
    posts = []
    seen = set()
    before = None

    for page in range(
        1,
        max_pages + 1,
    ):

        url = f"https://t.me/s/{channel}"

        if before:
            url += f"?before={before}"

        print(
            f"Reading {channel} "
            f"page {page}..."
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

            if not text:
                continue

            if not link:
                continue

            if link in seen:
                continue

            seen.add(link)

            page_posts.append(
                {
                    "text": text,
                    "link": link,
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

        ids = []

        for post in page_posts:

            match = re.search(
                r"/(\d+)$",
                post["link"],
            )

            if match:
                ids.append(
                    int(match.group(1))
                )

        if not ids:
            break

        next_before = str(
            min(ids)
        )

        if next_before == before:
            break

        before = next_before

    print(
        f"Total posts collected from "
        f"{channel}: {len(posts)}"
    )

    return posts


# =========================================================
# نرمال‌سازی برای جستجو
# =========================================================

def normalize_search(text):
    text = normalize_digits(
        clean_text(text)
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    return text


# =========================================================
# استخراج «قیمت لحظه ای» از یک بخش
# فقط همین فیلد معتبر است
# =========================================================

def parse_instant_price(
    section,
    minimum,
    maximum,
):
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

    value = parse_number(
        match.group(1),
        "rial",
    )

    if value is None:
        return None

    if not (
        minimum <= value <= maximum
    ):
        return None

    return value


# =========================================================
# استخراج بخش اختصاصی یک دارایی
# از عنوان دارایی تا شروع عنوان بعدی
# =========================================================

def extract_asset_section(
    text,
    start_pattern,
):
    text = normalize_search(text)

    match = re.search(
        start_pattern,
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    start = match.end()

    remaining = text[start:]

    # عنوان بخش بعدی در پست‌های TGJU
    # معمولاً با ⭕️ شروع می‌شود.
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
# کانال TGJU طلا
# فقط «قیمت لحظه ای» طلای ۱۸
# =========================================================

def parse_gold_post(text):

    patterns = [
        r"(?:^|\n)\s*⭕️\s*قیمت\s*طلای\s*(?:18|۱۸)\s*عیار",
        r"(?:^|\n)\s*قیمت\s*طلای\s*(?:18|۱۸)\s*عیار",
        r"(?:^|\n)\s*طلای\s*(?:18|۱۸)\s*عیار",
    ]

    for pattern in patterns:

        section = extract_asset_section(
            text,
            pattern,
        )

        if section is None:
            continue

        price = parse_instant_price(
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
# کانال TGJU ارز
# فقط «قیمت لحظه ای» #قیمت_دلار اصلی
# =========================================================

def parse_currency_post(text):

    text = normalize_search(
        text
    )

    match = re.search(
        r"#قیمت[_\s]*دلار\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return {}

    section_start = match.end()

    remaining = text[
        section_start:
    ]

    # پایان بخش دلار اصلی
    # قبل از دلار توافقی / سلیمانیه / هرات
    stop_patterns = [
        r"#قیمت[_\s]*دلار[_\s]*توافقی",
        r"#قیمت[_\s]*دلار[_\s]*سلیمانیه",
        r"#قیمت[_\s]*دلار[_\s]*هرات",
        r"⭕️\s*قیمت\s*دلار\s*دولتی",
        r"قیمت\s*دلار\s*دولتی",
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

    price = parse_instant_price(
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
# کانال TGJU سکه
# فقط «قیمت لحظه ای» هر بخش
# =========================================================

def parse_coin_post(text):

    text = normalize_search(
        text
    )

    result = {}

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

    for asset, config in (
        definitions.items()
    ):

        section = extract_asset_section(
            text,
            config["pattern"],
        )

        if section is None:
            continue

        price = parse_instant_price(
            section,
            config["min"],
            config["max"],
        )

        if price:

            result[asset] = price

    return result


# =========================================================
# دریافت آخرین پست معتبر
# =========================================================

def get_latest_parsed(
    channel_key,
):
    config = PRICE_SOURCES[
        channel_key
    ]

    posts = fetch_channel_posts(
        config["channel"]
    )

    parser = {
        "gold": parse_gold_post,
        "currency": parse_currency_post,
        "coin": parse_coin_post,
    }[
        channel_key
    ]

    latest = {}

    # پست جدیدتر را اول بررسی می‌کنیم
    for index, post in enumerate(
        reversed(posts),
        start=1,
    ):

        parsed = parser(
            post["text"]
        )

        if not parsed:
            continue

        print(
            f"{config['name']} "
            f"newest valid candidate #{index}:",
            parsed,
        )

        for asset, price in (
            parsed.items()
        ):

            if asset not in latest:

                latest[asset] = {
                    "price": price,
                    "link": post["link"],
                }

        if (
            channel_key == "gold"
            and "gold18" in latest
        ):
            break

        if (
            channel_key == "currency"
            and "dollar" in latest
        ):
            break

        if (
            channel_key == "coin"
            and all(
                asset in latest
                for asset in (
                    "coin",
                    "half",
                    "quarter",
                )
            )
        ):
            break

    print(
        f"{config['name']} "
        "LATEST INSTANT PRICES:"
    )

    print(
        json.dumps(
            latest,
            ensure_ascii=False,
            indent=2,
        )
    )

    return latest


# =========================================================
# دریافت همه قیمت‌های رسمی TGJU
# =========================================================

def get_official_prices():

    prices = {}

    # -----------------------------------------
    # طلای ۱۸
    # -----------------------------------------

    gold = get_latest_parsed(
        "gold"
    )

    if "gold18" not in gold:

        raise RuntimeError(
            "قیمت لحظه ای طلای ۱۸ "
            "در TGJU پیدا نشد."
        )

    prices["gold18"] = (
        gold["gold18"]["price"]
    )

    # -----------------------------------------
    # دلار
    # -----------------------------------------

    currency = get_latest_parsed(
        "currency"
    )

    if "dollar" not in currency:

        raise RuntimeError(
            "قیمت لحظه ای دلار "
            "در TGJU پیدا نشد."
        )

    prices["dollar"] = (
        currency["dollar"]["price"]
    )

    # -----------------------------------------
    # سکه
    # -----------------------------------------

    coin = get_latest_parsed(
        "coin"
    )

    for asset in (
        "coin",
        "half",
        "quarter",
    ):

        if asset not in coin:

            raise RuntimeError(
                f"قیمت لحظه ای {asset} "
                "در TGJU پیدا نشد."
            )

        prices[asset] = (
            coin[asset]["price"]
        )

    print(
        "================================"
    )

    print(
        "LATEST OFFICIAL TGJU "
        "INSTANT PRICES:"
    )

    print(
        json.dumps(
            prices,
            ensure_ascii=False,
            indent=2,
        )
    )

    return prices


# =========================================================
# قیمت قبلی
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


# =========================================================
# ذخیره قیمت فعلی
# =========================================================

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


# =========================================================
# ذخیره وضعیت ارسال
# =========================================================

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

📊 منبع: TGJU

🔸 طلا: https://t.me/tgjugold
🔸 سکه: https://t.me/tgjucoin
🔸 ارز: https://t.me/tgjucurrency

━━━━━━━━━━━━━━━━━━

🌙 زرین ماه
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""


# =========================================================
# ارسال به تلگرام
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

    if not result.get(
        "ok"
    ):

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

    # =====================================================
    # خاموشی 22:00 تا 08:59
    # =====================================================

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
                "between 22:00 and "
                "08:59 Tehran time."
            )

            return

    # =====================================================
    # جلوگیری از ارسال تکراری
    # =====================================================

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

    # =====================================================
    # قیمت قبلی
    # =====================================================

    previous = (
        load_previous_prices()
    )

    # =====================================================
    # دریافت قیمت لحظه‌ای واقعی
    # =====================================================

    prices = (
        get_official_prices()
    )

    # =====================================================
    # ساخت پیام
    # =====================================================

    message = build_message(
        prices,
        previous,
    )

    # =====================================================
    # ارسال
    # =====================================================

    print(
        "Sending message to Telegram..."
    )

    send_to_telegram(
        message
    )

    print(
        "Telegram message sent successfully."
    )

    # =====================================================
    # ذخیره وضعیت
    # =====================================================

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

    # =====================================================
    # ذخیره قیمت‌ها
    # =====================================================

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
