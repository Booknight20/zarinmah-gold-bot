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


# =========================================================
# دارایی‌ها
# =========================================================

ASSETS = [
    "gold18",
    "coin",
    "half",
    "quarter",
    "dollar",
]


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
# تبدیل عدد به تومان
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
# دریافت پست‌های کانال عمومی تلگرام
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

        url = (
            f"https://t.me/s/{channel}"
        )

        if before:
            url += (
                f"?before={before}"
            )

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

            node = wrapper.select_one(
                "div.tgme_widget_message_text"
            )

            date_node = wrapper.select_one(
                "a.tgme_widget_message_date"
            )

            if not node or not date_node:
                continue

            text = clean_text(
                node.get_text(
                    "\n",
                    strip=True,
                )
            )

            link = date_node.get(
                "href",
                "",
            )

            if (
                not text
                or not link
                or link in seen
            ):
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
                    int(
                        match.group(1)
                    )
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
# استخراج قیمت بعد از یک برچسب
# =========================================================

def first_price_after(
    text,
    label_regex,
    minimum,
    maximum,
    unit="rial",
):
    text = normalize_digits(
        clean_text(text)
    )

    pattern = (
        label_regex
        + r".{0,180}?"
        + r"([\d,]+)"
        + r"\s*(ریال|تومان|تومن)?"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return None

    detected_unit = unit

    if match.group(2) in (
        "تومان",
        "تومن",
    ):
        detected_unit = "toman"

    elif match.group(2) == "ریال":
        detected_unit = "rial"

    value = parse_number(
        match.group(1),
        detected_unit,
    )

    if (
        value
        and minimum <= value <= maximum
    ):
        return value

    return None


# =========================================================
# پارسر کانال TGJU طلا
# =========================================================

def parse_gold_post(
    text,
):
    patterns = [
        r"طلای\s*(?:18|۱۸)\s*عیار\s*(?:هر\s*گرم)?",
        r"هر\s*گرم\s*طلای\s*(?:18|۱۸)\s*عیار",
        r"گرم\s*طلای\s*(?:18|۱۸)\s*عیار",
    ]

    for pattern in patterns:

        value = first_price_after(
            text,
            pattern,
            100_000,
            500_000_000,
            "rial",
        )

        if value:
            return {
                "gold18": value
            }

    for line in clean_text(
        text
    ).splitlines():

        for pattern in patterns:

            value = first_price_after(
                line,
                pattern,
                100_000,
                500_000_000,
                "rial",
            )

            if value:
                return {
                    "gold18": value
                }

    return {}


# =========================================================
# پارسر کانال TGJU ارز
# =========================================================

def parse_currency_post(
    text,
):
    text = normalize_digits(
        clean_text(text)
    )

    # فقط نرخ اصلی #قیمت_دلار
    # نه توافقی، هرات، سلیمانیه و دولتی

    section_match = re.search(
        r"#قیمت[_\s]*دلار\b"
        r"(.*?)"
        r"(?=(?:🇺🇸|⭕️|#قیمت[_\s])|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not section_match:
        return {}

    section = section_match.group(1)

    match = re.search(
        r"قیمت\s*لحظه\s*ای"
        r"\s*[:：]?\s*"
        r"([\d,]+)"
        r"\s*ریال",
        section,
        flags=re.IGNORECASE,
    )

    if not match:
        return {}

    value = parse_number(
        match.group(1),
        "rial",
    )

    if (
        value
        and 100_000 <= value <= 1_000_000
    ):
        return {
            "dollar": value
        }

    return {}


# =========================================================
# پارسر کانال TGJU سکه
# =========================================================

def parse_coin_post(
    text,
):
    text = normalize_digits(
        clean_text(text)
    )

    result = {}

    patterns = {
        "coin": (
            r"سکه\s*امامی"
            r".{0,220}?"
            r"قیمت\s*لحظه\s*ای"
            r"\s*[:：]?\s*"
            r"([\d,]+)\s*ریال"
        ),
        "half": (
            r"نیم\s*سکه"
            r".{0,220}?"
            r"قیمت\s*لحظه\s*ای"
            r"\s*[:：]?\s*"
            r"([\d,]+)\s*ریال"
        ),
        "quarter": (
            r"ربع\s*سکه"
            r".{0,220}?"
            r"قیمت\s*لحظه\s*ای"
            r"\s*[:：]?\s*"
            r"([\d,]+)\s*ریال"
        ),
    }

    ranges = {
        "coin": (
            100_000_000,
            5_000_000_000,
        ),
        "half": (
            50_000_000,
            2_000_000_000,
        ),
        "quarter": (
            20_000_000,
            1_000_000_000,
        ),
    }

    for asset, pattern in patterns.items():

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if not match:

            label = {
                "coin": r"سکه\s*امامی",
                "half": r"نیم\s*سکه",
                "quarter": r"ربع\s*سکه",
            }[asset]

            value = first_price_after(
                text,
                label,
                ranges[asset][0],
                ranges[asset][1],
                "rial",
            )

            if value:
                result[asset] = value

            continue

        value = parse_number(
            match.group(1),
            "rial",
        )

        if (
            value
            and ranges[asset][0]
            <= value
            <= ranges[asset][1]
        ):
            result[asset] = value

    return result


# =========================================================
# دریافت آخرین قیمت از هر کانال
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

    for index, post in enumerate(
        posts
    ):

        parsed = parser(
            post["text"]
        )

        if parsed:

            print(
                f"{config['name']} "
                f"parsed post #{index + 1}:",
                parsed,
            )

        for asset, price in (
            parsed.items()
        ):

            if asset in latest:
                continue

            latest[asset] = {
                "price": price,
                "link": post["link"],
            }

        # وقتی قیمت مورد نیاز پیدا شد،
        # پست‌های قدیمی‌تر لازم نیست.

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
        "Parsed prices:"
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
# دریافت قیمت‌های رسمی TGJU
# =========================================================

def get_verified_prices():

    prices = {}

    # -----------------------------------------------------
    # طلا
    # -----------------------------------------------------

    gold_source = get_latest_parsed(
        "gold"
    )

    if "gold18" not in gold_source:

        raise RuntimeError(
            "قیمت طلای ۱۸ عیار "
            "از کانال رسمی TGJU پیدا نشد."
        )

    prices["gold18"] = (
        gold_source["gold18"]["price"]
    )

    # -----------------------------------------------------
    # دلار
    # -----------------------------------------------------

    currency_source = (
        get_latest_parsed(
            "currency"
        )
    )

    if "dollar" not in currency_source:

        raise RuntimeError(
            "قیمت دلار اصلی "
            "از کانال رسمی TGJU پیدا نشد."
        )

    prices["dollar"] = (
        currency_source["dollar"]["price"]
    )

    # -----------------------------------------------------
    # سکه‌ها
    # -----------------------------------------------------

    coin_source = get_latest_parsed(
        "coin"
    )

    for asset in (
        "coin",
        "half",
        "quarter",
    ):

        if asset not in coin_source:

            raise RuntimeError(
                f"قیمت {asset} "
                "از کانال رسمی TGJU پیدا نشد."
            )

        prices[asset] = (
            coin_source[asset]["price"]
        )

    print(
        "OFFICIAL TGJU VERIFIED PRICES:"
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

            return json.load(
                file
            )

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

            return json.load(
                file
            )

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

    update_time = (
        datetime.now(
            TEHRAN
        ).strftime(
            "%H:%M"
        )
    )

    return f"""🌙✨ زرین ماه
💎 قیمت رسمی TGJU طلا، سکه و دلار

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

📊 منابع رسمی TGJU:

🔸 https://t.me/tgjugold
🔸 https://t.me/tgjucoin
🔸 https://t.me/tgjucurrency

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

    if not result.get(
        "ok"
    ):

        raise RuntimeError(
            f"Telegram API error: "
            f"{result}"
        )


# =========================================================
# اجرای اصلی
# =========================================================

def main():

    print(
        "================================="
    )

    print(
        "Starting ZarinMah verified "
        "TGJU price bot..."
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
    # دریافت قیمت رسمی TGJU
    # =====================================================

    prices = (
        get_verified_prices()
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
# شروع برنامه
# =========================================================

if __name__ == "__main__":
    main()
