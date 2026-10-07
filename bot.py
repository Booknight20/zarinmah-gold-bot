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
# دارایی‌های موردنیاز
# =========================================================

ASSETS = [
    "gold18",
    "coin",
    "half",
    "quarter",
    "dollar",
]


# =========================================================
# میزان اختلاف قابل قبول بین منابع
# =========================================================

TOLERANCES = {
    "gold18": 0.007,    # 0.70%
    "coin": 0.010,      # 1.00%
    "half": 0.015,      # 1.50%
    "quarter": 0.015,   # 1.50%
    "dollar": 0.007,    # 0.70%
}


# =========================================================
# تبدیل اعداد فارسی و عربی
# =========================================================

def normalize_digits(value):

    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )

    return str(value).translate(
        table
    )


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
        "٬",
        ",",
    )

    text = text.replace(
        "،",
        ",",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# =========================================================
# تبدیل قیمت متنی به تومان
# =========================================================

def parse_number(
    value,
    unit="toman",
):
    """
    نمونه:
    269,500
    26,688,670
    2,603,950,000 ریال
    ۲۶۶۸۸۶۷۰ تومان
    """

    text = normalize_digits(
        clean_text(value)
    )

    if not text:
        return None

    text = text.replace(
        ",",
        "",
    )

    text = text.replace(
        "٬",
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

    # TGJU عمدتاً ریال اعلام می‌کند.
    if unit == "rial":
        number /= 10

    return int(
        round(number)
    )


# =========================================================
# دریافت صفحه عمومی تلگرام
# =========================================================

def fetch_channel_posts(
    channel,
    limit=80,
):
    """
    کانال عمومی Telegram را از t.me/s می‌خواند.
    """

    url = (
        f"https://t.me/s/{channel}"
    )

    print(
        "Reading Telegram source:",
        url,
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

    posts = []

    wrappers = soup.select(
        "div.tgme_widget_message_wrap"
    )

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
                " ",
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

        posts.append(
            {
                "text": text,
                "link": link,
            }
        )

        if len(posts) >= limit:
            break

    print(
        "Posts found:",
        len(posts),
    )

    return posts


# =========================================================
# استخراج قیمت از متن
# =========================================================

def extract_first_price(
    text,
    patterns,
    unit,
):
    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        price = parse_number(
            match.group(1),
            unit,
        )

        if (
            price is not None
            and price > 0
        ):
            return price

    return None


# =========================================================
# استخراج قیمت یک پست TGJU
# =========================================================

def parse_tgju_post(
    text,
):
    result = {}

    # -----------------------------------------
    # طلای 18 عیار
    # -----------------------------------------

    gold_match = re.search(
        r"(?:قیمت\s+طلای\s*18\s*عیار)"
        r".{0,500}?"
        r"قیمت\s+لحظه\s*ای\s*:\s*"
        r"([\d۰-۹,٬]+)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if gold_match:
        result["gold18"] = parse_number(
            gold_match.group(1),
            "rial",
        )

    # -----------------------------------------
    # سکه امامی تک‌فروشی
    # -----------------------------------------

    coin_match = re.search(
        r"سکه\s+امامی\s*"
        r"\(تک\s*فروشی\)\s*:\s*"
        r"([\d۰-۹,٬]+)",
        text,
        flags=re.IGNORECASE,
    )

    if coin_match:
        result["coin"] = parse_number(
            coin_match.group(1),
            "rial",
        )

    # -----------------------------------------
    # نیم‌سکه تک‌فروشی
    # -----------------------------------------

    half_match = re.search(
        r"نیم\s*سکه\s*"
        r"\(تک\s*فروشی\)\s*:\s*"
        r"([\d۰-۹,٬]+)",
        text,
        flags=re.IGNORECASE,
    )

    if half_match:
        result["half"] = parse_number(
            half_match.group(1),
            "rial",
        )

    # -----------------------------------------
    # ربع‌سکه تک‌فروشی
    # -----------------------------------------

    quarter_match = re.search(
        r"ربع\s*سکه\s*"
        r"\(تک\s*فروشی\)\s*:\s*"
        r"([\d۰-۹,٬]+)",
        text,
        flags=re.IGNORECASE,
    )

    if quarter_match:
        result["quarter"] = parse_number(
            quarter_match.group(1),
            "rial",
        )

    # -----------------------------------------
    # دلار آزاد
    # -----------------------------------------

    dollar_match = re.search(
        r"#قیمت[_\s]*دلار.*?"
        r"قیمت\s+لحظه\s*ای\s*:\s*"
        r"([\d۰-۹,٬]+)\s*ریال",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if dollar_match:
        result["dollar"] = parse_number(
            dollar_match.group(1),
            "rial",
        )

    # حالت دوم: قیمت ارزهای آزاد
    if "dollar" not in result:
        dollar_match = re.search(
            r"دلار\s*:\s*"
            r"([\d۰-۹,٬]+)\s*ریال",
            text,
            flags=re.IGNORECASE,
        )

        if dollar_match:
            result["dollar"] = parse_number(
                dollar_match.group(1),
                "rial",
            )

    return result


# =========================================================
# استخراج قیمت مثقال و نوسان
# =========================================================

def parse_toman_post(
    text,
):
    result = {}

    # -----------------------------------------
    # دلار فروش
    # -----------------------------------------

    dollar_match = re.search(
        r"دلار\s+آمریکا\s+فروش"
        r".*?:\s*"
        r"([\d۰-۹,٬]+)"
        r"\s*تومان",
        text,
        flags=re.IGNORECASE,
    )

    if dollar_match:
        result["dollar"] = parse_number(
            dollar_match.group(1),
            "toman",
        )

    # -----------------------------------------
    # اگر عبارت «فروش» پیدا نشد
    # -----------------------------------------

    if "dollar" not in result:

        dollar_match = re.search(
            r"دلار\s*:"
            r"\s*([\d۰-۹,٬]+)"
            r"\s*تومان",
            text,
            flags=re.IGNORECASE,
        )

        if dollar_match:
            result["dollar"] = parse_number(
                dollar_match.group(1),
                "toman",
            )

    # -----------------------------------------
    # طلا 18 عیار
    # -----------------------------------------

    gold_match = re.search(
        r"طلای\s*18\s*عیار"
        r"(?:\s*هر\s*گرم)?"
        r"\s*[:：]\s*"
        r"([\d۰-۹,٬]+)"
        r"\s*تومان",
        text,
        flags=re.IGNORECASE,
    )

    if gold_match:
        result["gold18"] = parse_number(
            gold_match.group(1),
            "toman",
        )

    # -----------------------------------------
    # سکه امامی
    # -----------------------------------------

    coin_match = re.search(
        r"سکه\s+امامی"
        r".*?:\s*"
        r"([\d۰-۹,٬]+)"
        r"\s*تومان",
        text,
        flags=re.IGNORECASE,
    )

    if coin_match:
        result["coin"] = parse_number(
            coin_match.group(1),
            "toman",
        )

    # -----------------------------------------
    # نیم سکه
    # -----------------------------------------

    half_match = re.search(
        r"نیم\s*سکه"
        r".*?:\s*"
        r"([\d۰-۹,٬]+)"
        r"\s*تومان",
        text,
        flags=re.IGNORECASE,
    )

    if half_match:
        result["half"] = parse_number(
            half_match.group(1),
            "toman",
        )

    # -----------------------------------------
    # ربع سکه
    # -----------------------------------------

    quarter_match = re.search(
        r"ربع\s*سکه"
        r".*?:\s*"
        r"([\d۰-۹,٬]+)"
        r"\s*تومان",
        text,
        flags=re.IGNORECASE,
    )

    if quarter_match:
        result["quarter"] = parse_number(
            quarter_match.group(1),
            "toman",
        )

    return result


# =========================================================
# گرفتن آخرین قیمت معتبر هر منبع
# =========================================================

def get_latest_source_prices(
    source_key,
    source_config,
):
    posts = fetch_channel_posts(
        source_config["channel"]
    )

    parsed_posts = []

    for post in posts:

        text = post["text"]

        if source_key == "tgju":
            prices = parse_tgju_post(
                text
            )

        else:
            prices = parse_toman_post(
                text
            )

        if prices:
            parsed_posts.append(
                {
                    "prices": prices,
                    "link": post.get(
                        "link",
                        "",
                    ),
                    "text": text,
                }
            )

    # جدیدترین پیام‌ها از تلگرام
    # بالاتر هستند، بنابراین اولین
    # مقدار موجود را نگه می‌داریم.
    latest = {}

    for post in parsed_posts:
        for asset, price in post[
            "prices"
        ].items():

            if (
                asset not in latest
                and price
                and price > 0
            ):
                latest[asset] = {
                    "price": price,
                    "link": post.get(
                        "link",
                        "",
                    ),
                }

    return latest


# =========================================================
# دریافت قیمت از هر سه منبع
# =========================================================

def get_all_source_prices():

    source_prices = {}

    for source_key, config in PRICE_SOURCES.items():

        print()
        print(
            "================================"
        )
        print(
            "Source:",
            config["name"],
        )

        try:

            source_prices[source_key] = (
                get_latest_source_prices(
                    source_key,
                    config,
                )
            )

            print(
                "Parsed:",
                source_prices[
                    source_key
                ],
            )

        except Exception as error:

            print(
                "Source failed:",
                config["name"],
                error,
            )

            source_prices[source_key] = {}

    return source_prices


# =========================================================
# پیدا کردن قیمت تأییدشده
# =========================================================

def validate_asset_price(
    asset,
    source_prices,
):
    candidates = []

    for source_key, prices in source_prices.items():

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

        item["difference"] = difference

        if difference <= tolerance:
            accepted.append(
                item
            )

    # حداقل دو منبع باید با هم سازگار باشند.
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

    return {
        "price": final_price,
        "sources": accepted,
        "all_sources": candidates,
    }


# =========================================================
# تأیید همه قیمت‌ها
# =========================================================

def build_verified_prices(
    source_prices,
):
    verified = {}

    for asset in ASSETS:

        result = validate_asset_price(
            asset,
            source_prices,
        )

        verified[asset] = (
            result["price"]
        )

        print(
            f"{asset}: "
            f"{result['price']:,} تومان"
        )

        print(
            "Accepted sources:",
            [
                item["source"]
                for item in result[
                    "sources"
                ]
            ]
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
# ارسال تلگرام
# =========================================================

def send_to_telegram(
    message,
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

    # ---------------------------------
    # ساعت خاموشی
    # ---------------------------------

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

    # ---------------------------------
    # جلوگیری از تکرار
    # ---------------------------------

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

    # ---------------------------------
    # قیمت قبلی
    # ---------------------------------

    previous_prices = (
        load_previous_prices()
    )

    # ---------------------------------
    # دریافت هر سه منبع
    # ---------------------------------

    print(
        "Fetching prices from "
        "TGJU, Mesghal and Navasan..."
    )

    source_prices = (
        get_all_source_prices()
    )

    print()
    print(
        "All source prices:"
    )

    print(
        json.dumps(
            source_prices,
            ensure_ascii=False,
            indent=2,
        )
    )

    # ---------------------------------
    # تطبیق و تأیید
    # ---------------------------------

    print()
    print(
        "Validating prices..."
    )

    prices = build_verified_prices(
        source_prices
    )

    print()
    print(
        "Verified prices:"
    )

    print(
        json.dumps(
            prices,
            ensure_ascii=False,
            indent=2,
        )
    )

    # ---------------------------------
    # ساخت پیام
    # ---------------------------------

    message = build_message(
        prices,
        previous_prices,
    )

    print(
        "Sending message to Telegram..."
    )

    # ---------------------------------
    # ارسال
    # ---------------------------------

    send_to_telegram(
        message
    )

    print(
        "Telegram message sent successfully."
    )

    # ---------------------------------
    # ثبت وضعیت فقط بعد از ارسال موفق
    # ---------------------------------

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

    # ---------------------------------
    # ذخیره قیمت تأییدشده
    # ---------------------------------

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
