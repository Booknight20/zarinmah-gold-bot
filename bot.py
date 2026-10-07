import os
import re
import json
import html
import statistics
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# =========================================================
# تنظیمات اصلی
# =========================================================

BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN"
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
# منابع قیمت
# =========================================================

PRICE_SOURCES = {
    "tgju": {
        "name": "TGJU",
        "channel": "tgjunews",
        "unit": "rial",
    },
    "mesghal": {
        "name": "مثقال",
        "channel": "mesghalsignal",
        "unit": "toman",
    },
    "navasan": {
        "name": "نوسان",
        "channel": "navasanchannel",
        "unit": "toman",
    },
}


# =========================================================
# دارایی‌های موردنظر
# =========================================================

ASSETS = [
    "gold18",
    "coin",
    "half",
    "quarter",
    "dollar",
]


# =========================================================
# حداکثر اختلاف قابل قبول
# =========================================================

TOLERANCES = {
    "gold18": 0.008,    # 0.8%
    "coin": 0.012,      # 1.2%
    "half": 0.015,      # 1.5%
    "quarter": 0.015,   # 1.5%
    "dollar": 0.008,    # 0.8%
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
# تبدیل قیمت به تومان
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
# استخراج اولین عدد بعد از یک عبارت
# =========================================================

def extract_after_label(
    text,
    label_pattern,
    default_unit,
):
    pattern = (
        label_pattern
        + r".{0,120}?"
        + r"([\d,]+)"
        + r"\s*(تومان|ریال)?"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return None

    number = match.group(1)
    explicit_unit = match.group(2)

    if explicit_unit == "ریال":
        unit = "rial"
    elif explicit_unit == "تومان":
        unit = "toman"
    else:
        unit = default_unit

    return parse_number(
        number,
        unit,
    )


# =========================================================
# واکشی کانال تلگرام با صفحه‌بندی
# =========================================================

def fetch_channel_posts(
    channel,
    max_pages=8,
):
    """
    Telegram در هر صفحه تعداد محدودی پیام نشان می‌دهد.
    بنابراین با before=ID صفحات قدیمی‌تر را هم می‌گیریم.
    """

    all_posts = []
    seen_links = set()

    before_id = None

    for page_number in range(
        1,
        max_pages + 1,
    ):
        if before_id:
            url = (
                f"https://t.me/s/{channel}"
                f"?before={before_id}"
            )
        else:
            url = (
                f"https://t.me/s/{channel}"
            )

        print()
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

            if not text_node:
                continue

            date_node = wrapper.select_one(
                "a.tgme_widget_message_date"
            )

            text = clean_text(
                text_node.get_text(
                    "\n",
                    strip=True,
                )
            )

            if not text:
                continue

            link = ""

            if date_node:
                link = date_node.get(
                    "href",
                    "",
                )

            if not link:
                continue

            if link in seen_links:
                continue

            seen_links.add(
                link
            )

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

        all_posts.extend(
            page_posts
        )

        # قدیمی‌ترین ID این صفحه
        post_ids = []

        for post in page_posts:
            match = re.search(
                r"/(\d+)$",
                post["link"],
            )

            if match:
                post_ids.append(
                    int(
                        match.group(1)
                    )
                )

        if not post_ids:
            break

        oldest_id = min(
            post_ids
        )

        # اگر همان ID قبلی بود یعنی صفحه‌بندی تمام شده
        if before_id == str(
            oldest_id
        ):
            break

        before_id = str(
            oldest_id
        )

    print(
        f"Total posts collected from "
        f"{channel}: {len(all_posts)}"
    )

    return all_posts


# =========================================================
# TGJU
# =========================================================

def parse_tgju_post(text):
    result = {}

    text = clean_text(
        text
    )

    # -----------------------------------------------------
    # دلار
    # -----------------------------------------------------

    dollar = extract_after_label(
        text,
        r"(?:#قیمت[_\s]*دلار|⭕️?\s*قیمت\s+دلار)",
        "rial",
    )

    if dollar:
        result["dollar"] = dollar

    # -----------------------------------------------------
    # طلای 18
    # -----------------------------------------------------

    gold = extract_after_label(
        text,
        r"(?:قیمت\s+)?طلای\s*(?:18|۱۸)\s*عیار",
        "rial",
    )

    if gold:
        result["gold18"] = gold

    # -----------------------------------------------------
    # سکه امامی
    # -----------------------------------------------------

    coin = extract_after_label(
        text,
        r"سکه\s*امامی\s*\(\s*تک\s*فروشی\s*\)",
        "rial",
    )

    if coin:
        result["coin"] = coin

    # -----------------------------------------------------
    # نیم سکه
    # -----------------------------------------------------

    half = extract_after_label(
        text,
        r"نیم\s*سکه\s*\(\s*تک\s*فروشی\s*\)",
        "rial",
    )

    if half:
        result["half"] = half

    # -----------------------------------------------------
    # ربع سکه
    # -----------------------------------------------------

    quarter = extract_after_label(
        text,
        r"ربع\s*سکه\s*\(\s*تک\s*فروشی\s*\)",
        "rial",
    )

    if quarter:
        result["quarter"] = quarter

    # حالت جایگزین TGJU برای نیم/ربع/سکه
    if "coin" not in result:
        result["coin"] = extract_after_label(
            text,
            r"سکه\s*امامی",
            "rial",
        )

    if "half" not in result:
        result["half"] = extract_after_label(
            text,
            r"نیم\s*سکه",
            "rial",
        )

    if "quarter" not in result:
        result["quarter"] = extract_after_label(
            text,
            r"ربع\s*سکه",
            "rial",
        )

    return {
        key: value
        for key, value in result.items()
        if value
    }


# =========================================================
# مثقال و نوسان
# =========================================================

def parse_toman_post(text):
    result = {}

    text = clean_text(
        text
    )

    # -----------------------------------------------------
    # دلار آمریکا فروش
    # -----------------------------------------------------

    dollar = extract_after_label(
        text,
        r"دلار\s*آمریکا\s*فروش",
        "toman",
    )

    if dollar:
        result["dollar"] = dollar

    # حالت ساده‌تر
    if "dollar" not in result:
        dollar = extract_after_label(
            text,
            r"دلار\s*آمریکا",
            "toman",
        )

        if dollar:
            result["dollar"] = dollar

    # -----------------------------------------------------
    # طلای 18
    # -----------------------------------------------------

    gold = extract_after_label(
        text,
        r"طلای\s*(?:18|۱۸)\s*عیار"
        r"(?:\s*هر\s*گرم)?",
        "toman",
    )

    if gold:
        result["gold18"] = gold

    # -----------------------------------------------------
    # سکه امامی
    # -----------------------------------------------------

    coin = extract_after_label(
        text,
        r"سکه\s*امامی",
        "toman",
    )

    if coin:
        result["coin"] = coin

    # -----------------------------------------------------
    # نیم سکه
    # -----------------------------------------------------

    half = extract_after_label(
        text,
        r"نیم\s*سکه",
        "toman",
    )

    if half:
        result["half"] = half

    # -----------------------------------------------------
    # ربع سکه
    # -----------------------------------------------------

    quarter = extract_after_label(
        text,
        r"ربع\s*سکه",
        "toman",
    )

    if quarter:
        result["quarter"] = quarter

    return {
        key: value
        for key, value in result.items()
        if value
    }


# =========================================================
# آخرین قیمت هر منبع
# =========================================================

def get_latest_source_prices(
    source_key,
    source_config,
):
    posts = fetch_channel_posts(
        source_config["channel"]
    )

    latest = {}

    # از جدیدترین پست به قدیمی‌تر می‌رویم.
    for post in posts:

        text = post.get(
            "text",
            "",
        )

        if source_key == "tgju":
            parsed = parse_tgju_post(
                text
            )
        else:
            parsed = parse_toman_post(
                text
            )

        if not parsed:
            continue

        for asset, price in parsed.items():

            if asset in latest:
                continue

            if not price:
                continue

            latest[asset] = {
                "price": price,
                "link": post.get(
                    "link",
                    "",
                ),
            }

    return latest


# =========================================================
# دریافت همه منابع
# =========================================================

def get_all_source_prices():

    result = {}

    for source_key, config in (
        PRICE_SOURCES.items()
    ):

        print()
        print(
            "================================"
        )

        print(
            "Source:",
            config["name"],
        )

        try:
            result[source_key] = (
                get_latest_source_prices(
                    source_key,
                    config,
                )
            )

            print(
                "Parsed prices:"
            )

            print(
                json.dumps(
                    result[source_key],
                    ensure_ascii=False,
                    indent=2,
                )
            )

        except Exception as error:

            print(
                "Source failed:",
                config["name"],
                error,
            )

            result[source_key] = {}

    return result


# =========================================================
# اعتبارسنجی یک دارایی
# =========================================================

def validate_asset_price(
    asset,
    source_prices,
):
    candidates = []

    for source_key, prices in (
        source_prices.items()
    ):
        item = prices.get(
            asset
        )

        if not item:
            continue

        price = item.get(
            "price"
        )

        if not price:
            continue

        candidates.append(
            {
                "source": source_key,
                "price": price,
                "link": item.get(
                    "link",
                    "",
                ),
            }
        )

    print()
    print(
        f"Validating {asset}..."
    )

    print(
        "Available candidates:",
        candidates,
    )

    if len(candidates) < 2:
        raise RuntimeError(
            f"برای {asset} "
            f"حداقل دو منبع معتبر موجود نیست."
        )

    values = [
        item["price"]
        for item in candidates
    ]

    median_price = statistics.median(
        values
    )

    tolerance = TOLERANCES.get(
        asset,
        0.01,
    )

    accepted = []

    for item in candidates:

        difference = (
            abs(
                item["price"]
                - median_price
            )
            / median_price
        )

        item["difference"] = (
            difference
        )

        print(
            f"{item['source']}: "
            f"{item['price']:,} "
            f"diff={difference:.4%}"
        )

        if (
            difference
            <= tolerance
        ):
            accepted.append(
                item
            )

    if len(accepted) < 2:

        details = ", ".join(
            [
                (
                    f"{item['source']}="
                    f"{item['price']:,}"
                )
                for item in candidates
            ]
        )

        raise RuntimeError(
            f"اختلاف منابع برای "
            f"{asset} غیرعادی است: "
            f"{details}"
        )

    accepted_values = [
        item["price"]
        for item in accepted
    ]

    final_price = int(
        round(
            statistics.median(
                accepted_values
            )
        )
    )

    return final_price


# =========================================================
# اعتبارسنجی همه قیمت‌ها
# =========================================================

def build_verified_prices(
    source_prices,
):
    verified = {}

    for asset in ASSETS:

        verified[asset] = (
            validate_asset_price(
                asset,
                source_prices,
            )
        )

        print(
            f"VERIFIED {asset}: "
            f"{verified[asset]:,} تومان"
        )

    return verified


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
    prices
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
    slot
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

def get_change_text(
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
    previous_prices,
):
    now = datetime.now(
        TEHRAN
    )

    update_time = now.strftime(
        "%H:%M"
    )

    previous_prices = (
        previous_prices or {}
    )

    gold_change = get_change_text(
        prices["gold18"],
        previous_prices.get(
            "gold18"
        ),
    )

    coin_change = get_change_text(
        prices["coin"],
        previous_prices.get(
            "coin"
        ),
    )

    half_change = get_change_text(
        prices["half"],
        previous_prices.get(
            "half"
        ),
    )

    quarter_change = get_change_text(
        prices["quarter"],
        previous_prices.get(
            "quarter"
        ),
    )

    dollar_change = get_change_text(
        prices["dollar"],
        previous_prices.get(
            "dollar"
        ),
    )

    return f"""🌙✨ زرین ماه
💎 قیمت تأییدشده طلا، سکه و دلار

━━━━━━━━━━━━━━━━━━

🟡 طلای ۱۸ عیار
💰 {prices["gold18"]:,} تومان
{gold_change}

🪙 سکه امامی
💰 {prices["coin"]:,} تومان
{coin_change}

🪙 نیم‌سکه
💰 {prices["half"]:,} تومان
{half_change}

🪙 ربع‌سکه
💰 {prices["quarter"]:,} تومان
{quarter_change}

💵 دلار آزاد
💰 {prices["dollar"]:,} تومان
{dollar_change}

━━━━━━━━━━━━━━━━━━

🕒 آخرین بروزرسانی: {update_time}

📊 مرجع قیمت:
TGJU + مثقال + نوسان

✅ قیمت‌ها پس از تطبیق حداقل دو منبع تأیید می‌شوند.

━━━━━━━━━━━━━━━━━━

🌙 زرین ماه
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""


# =========================================================
# ارسال به تلگرام
# =========================================================

def send_to_telegram(
    message
):
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    url = (
        "https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    data = {
        "chat_id": CHANNEL,
        "text": message,
    }

    response = requests.post(
        url,
        data=data,
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
        "================================"
    )

    print(
        "Starting ZarinMah verified "
        "price bot..."
    )

    print(
        "================================"
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

    current_slot = now.strftime(
        "%Y-%m-%d %H"
    )

    # -----------------------------------------
    # خاموشی 22:00 تا 08:59
    # -----------------------------------------

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

    # -----------------------------------------
    # جلوگیری از ارسال دوباره
    # -----------------------------------------

    if (
        scheduled_run
        or watchdog_retry
    ):

        status = load_send_status()

        last_hourly_slot = (
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
            last_hourly_slot
            == current_slot
        ):

            print(
                f"Hourly post for "
                f"{current_slot} "
                f"has already been sent."
            )

            print(
                "Skipping duplicate message."
            )

            return

    # -----------------------------------------
    # قیمت قبلی
    # -----------------------------------------

    previous_prices = (
        load_previous_prices()
    )

    # -----------------------------------------
    # دریافت منابع
    # -----------------------------------------

    print()
    print(
        "Fetching prices from:"
    )

    print(
        "1. TGJU"
    )

    print(
        "2. Mesghal"
    )

    print(
        "3. Navasan"
    )

    source_prices = (
        get_all_source_prices()
    )

    print()
    print(
        "================================"
    )

    print(
        "ALL SOURCE PRICES"
    )

    print(
        json.dumps(
            source_prices,
            ensure_ascii=False,
            indent=2,
        )
    )

    # -----------------------------------------
    # اعتبارسنجی
    # -----------------------------------------

    print()
    print(
        "================================"
    )

    print(
        "VALIDATING PRICES"
    )

    prices = build_verified_prices(
        source_prices
    )

    print()
    print(
        "================================"
    )

    print(
        "VERIFIED PRICES"
    )

    print(
        json.dumps(
            prices,
            ensure_ascii=False,
            indent=2,
        )
    )

    # -----------------------------------------
    # ساخت پیام
    # -----------------------------------------

    message = build_message(
        prices,
        previous_prices,
    )

    print(
        "Sending message to Telegram..."
    )

    # -----------------------------------------
    # ارسال
    # -----------------------------------------

    send_to_telegram(
        message
    )

    print(
        "Telegram message sent successfully."
    )

    # -----------------------------------------
    # ذخیره وضعیت
    # -----------------------------------------

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

    # -----------------------------------------
    # ذخیره قیمت‌های تأییدشده
    # -----------------------------------------

    save_current_prices(
        prices
    )

    print(
        "Verified prices saved."
    )

    print(
        "Bot completed successfully."
    )


if __name__ == "__main__":
    main()
