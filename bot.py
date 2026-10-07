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

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL = "@ZarinMahGold"

TEHRAN = ZoneInfo("Asia/Tehran")

PREVIOUS_FILE = "previous_prices.json"
STATUS_FILE = "send_status.json"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
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
# حداکثر اختلاف مجاز
# =========================================================

TOLERANCES = {
    "gold18": 0.008,
    "coin": 0.012,
    "half": 0.015,
    "quarter": 0.015,
    "dollar": 0.008,
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
# نرمال‌سازی جستجو
# =========================================================

def normalize_for_search(text):
    text = normalize_digits(clean_text(text))

    text = re.sub(r"\s+", " ", text)

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
# دریافت پست‌های کانال تلگرام
# =========================================================

def fetch_channel_posts(
    channel,
    max_pages=8,
):
    all_posts = []
    seen_links = set()
    before_id = None

    for page_number in range(
        1,
        max_pages + 1,
    ):

        url = f"https://t.me/s/{channel}"

        if before_id:
            url += f"?before={before_id}"

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

            seen_links.add(link)

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

        all_posts.extend(page_posts)

        post_ids = []

        for post in page_posts:

            match = re.search(
                r"/(\d+)$",
                post["link"],
            )

            if match:
                post_ids.append(
                    int(match.group(1))
                )

        if not post_ids:
            break

        next_before = str(
            min(post_ids)
        )

        if before_id == next_before:
            break

        before_id = next_before

    print(
        f"Total posts collected from "
        f"{channel}: {len(all_posts)}"
    )

    return all_posts


# =========================================================
# استخراج قیمت بعد از برچسب
# =========================================================

def extract_price_after_label(
    text,
    label_pattern,
    minimum,
    maximum,
    unit="toman",
):
    text = normalize_for_search(text)

    pattern = (
        label_pattern
        + r".{0,180}?"
        + r"([\d,]+)"
        + r"\s*(تومان|تومن|ریال)?"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return None

    explicit_unit = match.group(2)

    detected_unit = unit

    if explicit_unit == "ریال":
        detected_unit = "rial"

    elif explicit_unit in (
        "تومان",
        "تومن",
    ):
        detected_unit = "toman"

    price = parse_number(
        match.group(1),
        detected_unit,
    )

    if (
        price
        and minimum <= price <= maximum
    ):
        return price

    return None


# =========================================================
# استخراج قیمت از یک خط
# =========================================================

def extract_line_price(
    line,
    label_pattern,
    minimum,
    maximum,
    unit="toman",
):
    line = normalize_for_search(line)

    match = re.search(
        label_pattern,
        line,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    rest = line[match.end():]

    numbers = re.findall(
        r"([\d,]+)",
        rest,
    )

    for raw_number in numbers:

        digits = raw_number.replace(
            ",",
            "",
        )

        if len(digits) < 4:
            continue

        price = parse_number(
            raw_number,
            unit,
        )

        if (
            price
            and minimum <= price <= maximum
        ):
            return price

    return None


# =========================================================
# مثقال - دلار
# =========================================================

def extract_dollar_mesghal(text):

    patterns = [
        r"دلار\s*آمریکا\s*فروش",
        r"دلار\s*فروش",
    ]

    for pattern in patterns:

        price = extract_price_after_label(
            text,
            pattern,
            100_000,
            1_000_000,
            "toman",
        )

        if price:
            return price

        for line in clean_text(
            text
        ).splitlines():

            price = extract_line_price(
                line,
                pattern,
                100_000,
                1_000_000,
                "toman",
            )

            if price:
                return price

    return None


# =========================================================
# مثقال - طلای ۱۸
# =========================================================

def extract_gold18_mesghal(text):

    patterns = [
        r"طلای\s*(?:18|۱۸)\s*عیار",
        r"هر\s*گرم\s*طلای\s*(?:18|۱۸)",
    ]

    for pattern in patterns:

        price = extract_price_after_label(
            text,
            pattern,
            1_000_000,
            500_000_000,
            "toman",
        )

        if price:
            return price

        for line in clean_text(
            text
        ).splitlines():

            price = extract_line_price(
                line,
                pattern,
                1_000_000,
                500_000_000,
                "toman",
            )

            if price:
                return price

    return None


# =========================================================
# مثقال - سکه
# =========================================================

def extract_coin_mesghal(text):

    pattern = r"سکه\s*امامی"

    price = extract_price_after_label(
        text,
        pattern,
        10_000_000,
        1_000_000_000,
        "toman",
    )

    if price:
        return price

    for line in clean_text(
        text
    ).splitlines():

        price = extract_line_price(
            line,
            pattern,
            10_000_000,
            1_000_000_000,
            "toman",
        )

        if price:
            return price

    return None


# =========================================================
# مثقال - نیم سکه
# =========================================================

def extract_half_mesghal(text):

    pattern = r"نیم\s*سکه"

    price = extract_price_after_label(
        text,
        pattern,
        5_000_000,
        500_000_000,
        "toman",
    )

    if price:
        return price

    for line in clean_text(
        text
    ).splitlines():

        price = extract_line_price(
            line,
            pattern,
            5_000_000,
            500_000_000,
            "toman",
        )

        if price:
            return price

    return None


# =========================================================
# مثقال - ربع سکه
# =========================================================

def extract_quarter_mesghal(text):

    pattern = r"ربع\s*سکه"

    price = extract_price_after_label(
        text,
        pattern,
        2_000_000,
        300_000_000,
        "toman",
    )

    if price:
        return price

    for line in clean_text(
        text
    ).splitlines():

        price = extract_line_price(
            line,
            pattern,
            2_000_000,
            300_000_000,
            "toman",
        )

        if price:
            return price

    return None


# =========================================================
# طلای ۱۸ عمومی
# =========================================================

def extract_gold18(
    text,
    unit,
):
    text = normalize_for_search(text)

    patterns = [
        (
            r"طلای\s*(?:18|۱۸)\s*عیار"
            r".{0,160}?"
            r"([\d,]+)"
            r"\s*(تومان|تومن|ریال)?"
        ),
        (
            r"طلای\s*(?:18|۱۸)"
            r".{0,160}?"
            r"([\d,]+)"
            r"\s*(تومان|تومن|ریال)?"
        ),
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if not match:
            continue

        detected_unit = unit

        if match.group(2) == "ریال":
            detected_unit = "rial"

        elif match.group(2) in (
            "تومان",
            "تومن",
        ):
            detected_unit = "toman"

        price = parse_number(
            match.group(1),
            detected_unit,
        )

        if (
            price
            and 100_000 <= price <= 500_000_000
        ):
            return price

    return None


# =========================================================
# دلار عمومی
# =========================================================

def extract_dollar(
    text,
    unit,
):
    text = normalize_for_search(text)

    candidates = []

    # فقط #قیمت_دلار اصلی TGJU
    tgju_match = re.search(
        r"#قیمت[_\s]*دلار\b"
        r"(.*?)"
        r"(?:(?:🇺🇸|⭕️|#قیمت[_\s])|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if tgju_match:

        section = tgju_match.group(1)

        live_match = re.search(
            r"قیمت\s*لحظه\s*ای"
            r"\s*[:：]?\s*"
            r"([\d,]+)"
            r"\s*ریال",
            section,
            flags=re.IGNORECASE,
        )

        if live_match:

            price = parse_number(
                live_match.group(1),
                "rial",
            )

            if (
                price
                and 100_000 <= price <= 1_000_000
            ):
                candidates.append(
                    price
                )

        if not candidates:

            for raw_number in re.findall(
                r"([\d,]+)\s*ریال",
                section,
            ):

                price = parse_number(
                    raw_number,
                    "rial",
                )

                if (
                    price
                    and 100_000 <= price <= 1_000_000
                ):
                    candidates.append(
                        price
                    )

    # منابع تومانی
    for pattern in [
        r"دلار\s*آمریکا\s*فروش",
        r"دلار\s*فروش",
    ]:

        price = extract_price_after_label(
            text,
            pattern,
            100_000,
            1_000_000,
            "toman",
        )

        if price:
            candidates.append(
                price
            )

    if not candidates:
        return None

    return int(
        round(
            statistics.median(
                candidates
            )
        )
    )


# =========================================================
# سکه عمومی
# =========================================================

def extract_coin(
    text,
    unit,
):
    pattern = (
        r"سکه\s*امامی"
        r".{0,160}?"
        r"([\d,]+)"
        r"\s*(تومان|تومن|ریال)?"
    )

    for match in re.finditer(
        pattern,
        normalize_for_search(text),
        flags=re.IGNORECASE | re.DOTALL,
    ):

        detected_unit = unit

        if match.group(2) == "ریال":
            detected_unit = "rial"

        elif match.group(2) in (
            "تومان",
            "تومن",
        ):
            detected_unit = "toman"

        price = parse_number(
            match.group(1),
            detected_unit,
        )

        if (
            price
            and 10_000_000 <= price <= 1_000_000_000
        ):
            return price

    return None


# =========================================================
# نیم سکه عمومی
# =========================================================

def extract_half(
    text,
    unit,
):
    pattern = (
        r"نیم\s*سکه"
        r".{0,140}?"
        r"([\d,]+)"
        r"\s*(تومان|تومن|ریال)?"
    )

    for match in re.finditer(
        pattern,
        normalize_for_search(text),
        flags=re.IGNORECASE | re.DOTALL,
    ):

        detected_unit = unit

        if match.group(2) == "ریال":
            detected_unit = "rial"

        elif match.group(2) in (
            "تومان",
            "تومن",
        ):
            detected_unit = "toman"

        price = parse_number(
            match.group(1),
            detected_unit,
        )

        if (
            price
            and 5_000_000 <= price <= 500_000_000
        ):
            return price

    return None


# =========================================================
# ربع سکه عمومی
# =========================================================

def extract_quarter(
    text,
    unit,
):
    pattern = (
        r"ربع\s*سکه"
        r".{0,140}?"
        r"([\d,]+)"
        r"\s*(تومان|تومن|ریال)?"
    )

    for match in re.finditer(
        pattern,
        normalize_for_search(text),
        flags=re.IGNORECASE | re.DOTALL,
    ):

        detected_unit = unit

        if match.group(2) == "ریال":
            detected_unit = "rial"

        elif match.group(2) in (
            "تومان",
            "تومن",
        ):
            detected_unit = "toman"

        price = parse_number(
            match.group(1),
            detected_unit,
        )

        if (
            price
            and 2_000_000 <= price <= 300_000_000
        ):
            return price

    return None


# =========================================================
# پارسر TGJU
# =========================================================

def parse_tgju_post(text):

    result = {}

    text = clean_text(text)

    parsers = {
        "dollar": lambda: extract_dollar(
            text,
            "rial",
        ),
        "gold18": lambda: extract_gold18(
            text,
            "rial",
        ),
        "coin": lambda: extract_coin(
            text,
            "rial",
        ),
        "half": lambda: extract_half(
            text,
            "rial",
        ),
        "quarter": lambda: extract_quarter(
            text,
            "rial",
        ),
    }

    for asset, parser in parsers.items():

        value = parser()

        if value:
            result[asset] = value

    return result


# =========================================================
# پارسر اختصاصی مثقال
# =========================================================

def parse_mesghal_post(text):

    result = {}

    text = clean_text(text)

    parsers = {
        "dollar": extract_dollar_mesghal,
        "gold18": extract_gold18_mesghal,
        "coin": extract_coin_mesghal,
        "half": extract_half_mesghal,
        "quarter": extract_quarter_mesghal,
    }

    for asset, parser in parsers.items():

        value = parser(text)

        if value:

            result[asset] = value

    return result


# =========================================================
# پارسر نوسان
# =========================================================

def parse_toman_post(text):

    result = {}

    text = clean_text(text)

    parsers = {
        "dollar": lambda: extract_dollar(
            text,
            "toman",
        ),
        "gold18": lambda: extract_gold18(
            text,
            "toman",
        ),
        "coin": lambda: extract_coin(
            text,
            "toman",
        ),
        "half": lambda: extract_half(
            text,
            "toman",
        ),
        "quarter": lambda: extract_quarter(
            text,
            "toman",
        ),
    }

    for asset, parser in parsers.items():

        value = parser()

        if value:
            result[asset] = value

    return result


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

    for post in posts:

        text = post.get(
            "text",
            "",
        )

        if source_key == "tgju":

            parsed = parse_tgju_post(
                text
            )

        elif source_key == "mesghal":

            parsed = parse_mesghal_post(
                text
            )

        else:

            parsed = parse_toman_post(
                text
            )

        if parsed:

            print(
                f"{source_config['name']} "
                f"parsed post:",
                parsed,
            )

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

        if all(
            asset in latest
            for asset in ASSETS
        ):
            break

    # اگر مثقال باز هم چیزی پیدا نکرد،
    # نمونه واقعی پست را چاپ می‌کنیم.
    if (
        source_key == "mesghal"
        and not latest
        and posts
    ):

        print(
            "WARNING: MESGHAL parser "
            "found no prices."
        )

        print(
            "MESGHAL SAMPLE START"
        )

        print(
            posts[0].get(
                "text",
                "",
            )
        )

        print(
            "MESGHAL SAMPLE END"
        )

    return latest


# =========================================================
# دریافت همه منابع
# =========================================================

def get_all_source_prices():

    result = {}

    for source_key, config in (
        PRICE_SOURCES.items()
    ):

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
# اعتبارسنجی یک قیمت
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
            (
                f"{item['source']}="
                f"{item['price']:,}"
            )
            for item in candidates
        )

        raise RuntimeError(
            f"اختلاف منابع برای "
            f"{asset} غیرعادی است: "
            f"{details}"
        )

    final_price = int(
        round(
            statistics.median(
                [
                    item["price"]
                    for item in accepted
                ]
            )
        )
    )

    print(
        "Accepted sources for "
        f"{asset}: "
        + ", ".join(
            item["source"]
            for item in accepted
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

    return "⚪ ➖ بدون تغییر"


# =========================================================
# ساخت پیام
# =========================================================

def build_message(
    prices,
    previous_prices,
):

    update_time = datetime.now(
        TEHRAN
    ).strftime(
        "%H:%M"
    )

    previous_prices = (
        previous_prices or {}
    )

    return f"""🌙✨ زرین ماه
💎 قیمت تأییدشده طلا، سکه و دلار

━━━━━━━━━━━━━━━━━━

🟡 طلای ۱۸ عیار
💰 {prices["gold18"]:,} تومان
{get_change_text(prices["gold18"], previous_prices.get("gold18"))}

🪙 سکه امامی
💰 {prices["coin"]:,} تومان
{get_change_text(prices["coin"], previous_prices.get("coin"))}

🪙 نیم‌سکه
💰 {prices["half"]:,} تومان
{get_change_text(prices["half"], previous_prices.get("half"))}

🪙 ربع‌سکه
💰 {prices["quarter"]:,} تومان
{get_change_text(prices["quarter"], previous_prices.get("quarter"))}

💵 دلار آزاد
💰 {prices["dollar"]:,} تومان
{get_change_text(prices["dollar"], previous_prices.get("dollar"))}

━━━━━━━━━━━━━━━━━━

🕒 آخرین بروزرسانی: {update_time}

📊 مراجع قیمت:
TGJU + مثقال + نوسان

✅ هر قیمت فقط در صورت تطبیق حداقل دو منبع منتشر می‌شود.

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
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
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

    print(
        "Tehran hour:",
        now.hour,
    )

    current_slot = now.strftime(
        "%Y-%m-%d %H"
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
                "has already been sent."
            )

            print(
                "Skipping duplicate message."
            )

            return

    previous_prices = (
        load_previous_prices()
    )

    print(
        "Fetching prices from:"
    )

    print("1. TGJU")
    print("2. Mesghal")
    print("3. Navasan")

    source_prices = (
        get_all_source_prices()
    )

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

    print(
        "================================"
    )

    print(
        "VALIDATING PRICES"
    )

    prices = build_verified_prices(
        source_prices
    )

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

    message = build_message(
        prices,
        previous_prices,
    )

    print(
        "Sending message to Telegram..."
    )

    send_to_telegram(
        message
    )

    print(
        "Telegram message sent successfully."
    )

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
# اجرا
# =========================================================

if __name__ == "__main__":
    main()
