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

ASSETS = (
    "gold18",
    "coin",
    "half",
    "quarter",
    "dollar",
)


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


# =========================================================
# TGJU ارز
# =========================================================

def parse_currency_post(
    text,
):
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

def parse_coin_post(
    text,
):
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

    for asset, config in (
        definitions.items()
    ):

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
# تشخیص تازگی پست
# =========================================================

def parse_post_datetime(value):
    if not value:
        return None

    try:
        text = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=TEHRAN)

        return parsed.astimezone(TEHRAN)

    except (ValueError, TypeError):
        return None


def post_age_minutes(post):
    posted_at = parse_post_datetime(
        post.get("posted_at")
    )

    if posted_at is None:
        return None

    return (
        datetime.now(TEHRAN) - posted_at
    ).total_seconds() / 60


def is_post_fresh(post, max_age_minutes):
    age = post_age_minutes(post)

    # اگر زمان پست قابل‌تشخیص نباشد، آن را به‌عنوان قیمت تازه قبول نمی‌کنیم.
    if age is None:
        return False

    # اختلاف جزئی ساعت را تحمل می‌کنیم؛ پست بیش از ۱۰ دقیقه در آینده معتبر نیست.
    return -10 <= age <= max_age_minutes


# =========================================================
# آخرین قیمت یک دارایی از TGJU
# =========================================================

def get_latest_asset_price(
    channel_key,
    asset,
    require_fresh=False,
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

    for post in posts:

        parsed = parser(
            post["text"]
        )

        if asset not in parsed:
            continue

        price = parsed[asset]

        if require_fresh and not is_post_fresh(
            post,
            MAX_TGJU_AGE_MINUTES,
        ):
            print(
                "TGJU price is missing or older than "
                f"{MAX_TGJU_AGE_MINUTES} minutes for {asset}."
            )
            print(
                "Stale TGJU post:",
                post.get("link"),
                "posted_at=",
                post.get("posted_at"),
            )
            raise RuntimeError(
                f"قیمت تازه برای {asset} در TGJU موجود نیست."
            )

        print(
            "LATEST TGJU MATCH"
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
            "posted_at": post.get("posted_at"),
        }

    raise RuntimeError(
        f"قیمت لحظه‌ای {asset} "
        f"در کانال {config['channel']} "
        f"پیدا نشد."
    )


# =========================================================
# استخراج قیمت از کانال نوسان (قیمت‌ها به تومان هستند)
# =========================================================

def extract_navasan_line_price(line):
    line = normalize_digits(clean_text(line))

    match = re.search(
        r"[:：]\s*([\d,]+)(?:\s*تومان)?\s*$",
        line,
        flags=re.IGNORECASE,
    )

    if not match:
        # بعضی پست‌های نوسان برای ارز فقط عدد را بدون دونقطه نشان می‌دهند.
        match = re.search(
            r"(?<![\w])([\d]{1,3}(?:,[\d]{3})+|[\d]{4,})(?:\s*تومان)?\s*$",
            line,
            flags=re.IGNORECASE,
        )

    if not match:
        return None

    try:
        return int(match.group(1).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_navasan_post(text, asset):
    text = normalize_digits(clean_text(text))
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    line_patterns = {
        "gold18": re.compile(r"طلای\s*(?:18|۱۸)\s*عیار", re.IGNORECASE),
        "coin": re.compile(r"سکه\s*امامی", re.IGNORECASE),
        "half": re.compile(r"نیم\s*سکه", re.IGNORECASE),
        "quarter": re.compile(r"ربع\s*سکه", re.IGNORECASE),
    }

    if asset == "dollar":
        matching_lines = []
        for line in lines:
            normalized_line = clean_text(line).replace("ي", "ی").replace("ك", "ک").lower()
            if "دلار آمریکا" not in normalized_line:
                continue
            if any(term in normalized_line for term in ("دلار کانادا", "هرات", "سلیمانیه", "توافقی")):
                continue
            if "خرید" in normalized_line:
                continue
            # اگر قیمت فروش موجود باشد، از همان استفاده می‌کنیم.
            if "فروش" in normalized_line:
                matching_lines.insert(0, line)
            else:
                matching_lines.append(line)

        for line in matching_lines:
            price = extract_navasan_line_price(line)
            if price and 100_000 <= price <= 2_000_000:
                return price
        return None

    pattern = line_patterns.get(asset)
    if pattern is None:
        return None

    bounds = {
        "gold18": (100_000, 500_000_000),
        "coin": (100_000_000, 5_000_000_000),
        "half": (50_000_000, 2_000_000_000),
        "quarter": (20_000_000, 1_000_000_000),
    }
    minimum, maximum = bounds[asset]

    for line in lines:
        if not pattern.search(line):
            continue
        price = extract_navasan_line_price(line)
        if price and minimum <= price <= maximum:
            return price

    return None


def get_latest_navasan_asset_price(posts, asset):
    for post in posts:
        price = parse_navasan_post(
            post.get("text", ""),
            asset,
        )

        if price is None:
            continue

        if not is_post_fresh(
            post,
            MAX_NAVASAN_AGE_MINUTES,
        ):
            print(
                "Navasan price is stale or its timestamp is unknown:",
                asset,
                post.get("link"),
                post.get("posted_at"),
            )
            return None

        print(
            "LATEST NAVASAN MATCH:",
            asset,
            f"{price:,} toman",
            post.get("link"),
        )

        return {
            "price": price,
            "link": post.get("link", ""),
            "message_id": post.get("message_id"),
            "posted_at": post.get("posted_at"),
        }

    return None


def get_hourly_prices_with_fallback():
    """برای هر دارایی، اول نرخ تازه TGJU و سپس آخرین نرخ تازه نوسان را می‌گیرد."""
    global PRICE_METADATA
    PRICE_METADATA = {}

    asset_sources = {
        "gold18": "gold",
        "dollar": "currency",
        "coin": "coin",
        "half": "coin",
        "quarter": "coin",
    }

    result = {}
    navasan_posts = None

    for asset, channel_key in asset_sources.items():
        official = None
        try:
            official = get_latest_asset_price(
                channel_key,
                asset,
                require_fresh=True,
            )
        except Exception as error:
            print(
                f"TGJU not usable for {asset}; trying Navasan:",
                error,
            )

        if official:
            result[asset] = official["price"]
            PRICE_METADATA[asset] = {
                "source": "tgju",
                "source_key": channel_key,
                "source_name": PRICE_SOURCES[channel_key]["name"],
                "link": official.get("link", ""),
                "posted_at": official.get("posted_at"),
            }
            continue

        if navasan_posts is None:
            try:
                navasan_posts = fetch_channel_posts(
                    NAVASAN_CHANNEL,
                    max_pages=3,
                )
            except Exception as error:
                print("Could not read Navasan channel:", error)
                navasan_posts = []

        fallback = get_latest_navasan_asset_price(
            navasan_posts,
            asset,
        )

        if not fallback:
            raise RuntimeError(
                f"برای {asset} نه قیمت تازه TGJU پیدا شد و نه قیمت تازه در نوسان."
            )

        result[asset] = fallback["price"]
        PRICE_METADATA[asset] = {
            "source": "navasan",
            "source_key": "navasan",
            "source_name": "نوسان",
            "link": fallback.get("link", ""),
            "posted_at": fallback.get("posted_at"),
        }

    print("================================")
    print("HOURLY PRICES WITH SOURCE FALLBACK:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("PRICE SOURCES:")
    print(json.dumps(PRICE_METADATA, ensure_ascii=False, indent=2))
    return result


# =========================================================
# آخرین قیمت‌های رسمی TGJU (بدون الزام تازگی؛ برای سازگاری تابع قدیمی)
# =========================================================

def get_official_prices():

    result = {}

    gold = get_latest_asset_price(
        "gold",
        "gold18",
    )

    result["gold18"] = (
        gold["price"]
    )

    dollar = get_latest_asset_price(
        "currency",
        "dollar",
    )

    result["dollar"] = (
        dollar["price"]
    )

    coin = get_latest_asset_price(
        "coin",
        "coin",
    )

    result["coin"] = (
        coin["price"]
    )

    half = get_latest_asset_price(
        "coin",
        "half",
    )

    result["half"] = (
        half["price"]
    )

    quarter = get_latest_asset_price(
        "coin",
        "quarter",
    )

    result["quarter"] = (
        quarter["price"]
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
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    return result


# =========================================================
# سازگاری با daily_analysis.py قدیمی
# =========================================================

def get_all_prices():
    """
    تابع قدیمی که daily_analysis.py استفاده می‌کند.

    برای سازگاری، همان قیمت‌های رسمی و لحظه‌ای TGJU
    را برمی‌گرداند.
    """

    return get_official_prices()


# =========================================================
# قیمت‌های قبلی
# =========================================================

def load_previous_prices():
    """Return the fixed daily reference, not the previous hourly price."""
    if not os.path.exists(PREVIOUS_FILE):
        return None

    try:
        with open(PREVIOUS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        today = datetime.now(TEHRAN).date().isoformat()

        if data.get("_daily_date") == today:
            reference = data.get("_daily_prices") or {}
            sources = data.get("_daily_sources") or {}
            if reference:
                result = dict(reference)
                result["_sources"] = sources
                return result

        # First run of a new day: compare against the last saved prices
        # from the previous day.
        result = {
            asset: data[asset]
            for asset in ASSETS
            if asset in data
        }
        result["_sources"] = data.get("_sources", {})
        return result if any(asset in result for asset in ASSETS) else None

    except Exception as error:
        print("Could not load previous prices:", error)
        return None


def save_current_prices(prices):
    """Save current prices while keeping a stable daily comparison baseline."""
    today = datetime.now(TEHRAN).date().isoformat()
    old_data = {}

    if os.path.exists(PREVIOUS_FILE):
        try:
            with open(PREVIOUS_FILE, "r", encoding="utf-8") as file:
                old_data = json.load(file)
        except Exception as error:
            print("Could not read old prices while saving:", error)

    if old_data.get("_daily_date") == today and old_data.get("_daily_prices"):
        daily_prices = old_data["_daily_prices"]
        daily_sources = old_data.get("_daily_sources", {})
    else:
        # On the first run of the day, use yesterday's last saved prices.
        daily_prices = {
            asset: old_data[asset]
            for asset in ASSETS
            if asset in old_data
        }
        daily_sources = old_data.get("_sources", {})

        # If this is the very first run ever, establish today's first
        # successful prices as the baseline for later posts today.
        if not daily_prices:
            daily_prices = dict(prices)
            daily_sources = {
                asset: info.get("source", "tgju")
                for asset, info in PRICE_METADATA.items()
            }

    data = dict(prices)
    data["_sources"] = {
        asset: info.get("source", "tgju")
        for asset, info in PRICE_METADATA.items()
    }
    data["_saved_at"] = datetime.now(TEHRAN).isoformat()
    data["_daily_date"] = today
    data["_daily_prices"] = daily_prices
    data["_daily_sources"] = daily_sources

    with open(PREVIOUS_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


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


def save_send_status(
    status,
):
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


def mark_telegram_sent(
    slot,
):
    status = load_send_status()

    status["telegram_hourly"] = {
        "slot": slot,
        "sent_at": datetime.now(
            TEHRAN
        ).isoformat(),
    }

    save_send_status(
        status
    )


def mark_eitaa_sent(
    slot,
):
    status = load_send_status()

    status["eitaa_hourly"] = {
        "slot": slot,
        "sent_at": datetime.now(
            TEHRAN
        ).isoformat(),
    }

    save_send_status(
        status
    )


def mark_hourly_complete(
    slot,
):
    status = load_send_status()

    status["hourly"] = {
        "slot": slot,
        "sent_at": datetime.now(
            TEHRAN
        ).isoformat(),
    }

    save_send_status(
        status
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

    return "⚪ ➖ بدون تغییر"


# =========================================================
# نمایش منبع انتخاب‌شده برای هر قیمت
# =========================================================

def price_source_line(asset):
    info = PRICE_METADATA.get(asset, {})
    if info.get("source") == "navasan":
        return "📍 منبع جایگزین: نوسان"
    if info.get("source") == "tgju":
        return "📍 منبع: TGJU"
    return ""


def change_text_for_asset(asset, current, previous_prices):
    previous_prices = previous_prices or {}
    previous_price = previous_prices.get(asset)

    if previous_price is None:
        return "🆕 اولین ثبت"

    previous_sources = previous_prices.get("_sources", {})
    previous_source = previous_sources.get(asset)

    # فایل قیمت قدیمی قبل از اضافه‌شدن منبع جایگزین، فقط قیمت TGJU داشت.
    if previous_source is None:
        previous_source = "tgju"

    current_source = PRICE_METADATA.get(asset, {}).get("source")

    # اختلاف نرخ دو منبع ممکن است با تغییر واقعی بازار اشتباه گرفته شود.
    if (
        previous_source
        and current_source
        and previous_source != current_source
    ):
        return "⚪ تغییر منبع؛ مقایسه مستقیم انجام نشد"

    return change_text(current, previous_price)


def used_source_footer():
    used_tgju_keys = {
        info.get("source_key")
        for info in PRICE_METADATA.values()
        if info.get("source") == "tgju"
    }

    parts = ["📊 منابع قیمت:"]

    if "gold" in used_tgju_keys:
        parts.append("🔸 TGJU طلا: https://t.me/tgjugold")
    if "coin" in used_tgju_keys:
        parts.append("🔸 TGJU سکه: https://t.me/tgjucoin")
    if "currency" in used_tgju_keys:
        parts.append("🔸 TGJU ارز: https://t.me/tgjucurrency")

    if any(
        info.get("source") == "navasan"
        for info in PRICE_METADATA.values()
    ):
        parts.append("🔹 نوسان: https://t.me/navasanchannel")

    return "\n".join(parts)


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

    def format_asset(title, asset):
        source_line = price_source_line(asset)
        source_text = f"\n{source_line}" if source_line else ""
        return (
            f"{title}\n"
            f"💰 {prices[asset]:,} تومان\n"
            f"{change_text_for_asset(asset, prices[asset], previous)}"
            f"{source_text}"
        )

    asset_sections = [
        format_asset("🟡 طلای ۱۸ عیار", "gold18"),
        format_asset("🪙 سکه امامی", "coin"),
        format_asset("🪙 نیم‌سکه", "half"),
        format_asset("🪙 ربع‌سکه", "quarter"),
        format_asset("💵 دلار آزاد", "dollar"),
    ]

    return (
        "🌙✨ زرین ماه | قیمت بازار\n"
        "💎 قیمت طلا، سکه و دلار\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        + "\n\n".join(asset_sections)
        + "\n\n━━━━━━━━━━━━━━━━━━\n"
        + f"🕒 زمان ارسال: {update_time}\n\n"
        + used_source_footer()
        + "\n\n━━━━━━━━━━━━━━━━━━\n"
        "🌙 زرین ماه | طلای کم‌اجرت\n"
        "📲 @ZarinMahGold\n"
    )


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
            f"Telegram API error: {result}"
        )


# =========================================================
# ارسال صحیح به ایتایار
# =========================================================

def send_to_eitaa(
    message,
):
    if not EITAAYAR_TOKEN:
        raise RuntimeError(
            "EITAAYAR_TOKEN "
            "تنظیم نشده است."
        )

    if not EITAA_CHAT_ID:
        raise RuntimeError(
            "EITAA_CHAT_ID "
            "تنظیم نشده است."
        )

    token = EITAAYAR_TOKEN.strip()

    chat_id = EITAA_CHAT_ID.strip()

    chat_id = chat_id.lstrip("@")

    url = (
        f"https://eitaayar.ir/api/"
        f"{token}/sendMessage"
    )

    data = {
        "chat_id": chat_id,
        "text": message,
    }

    print(
        "Sending message to Eitaa..."
    )

    print(
        "Eitaa chat_id:",
        "***",
    )

    response = requests.post(
        url,
        data=data,
        timeout=30,
    )

    print(
        "Eitaa HTTP status:",
        response.status_code,
    )

    print(
        "Eitaa response:",
        response.text,
    )

    response.raise_for_status()

    try:
        result = response.json()

    except ValueError:
        raise RuntimeError(
            "Eitaa API پاسخ JSON معتبر "
            "برنگرداند."
        )

    if not result.get(
        "ok"
    ):
        raise RuntimeError(
            f"Eitaa API error: {result}"
        )

    print(
        "Eitaa message sent successfully."
    )

    return result


# =========================================================
# اجرای اصلی
# =========================================================

def main():

    print(
        "================================="
    )

    print(
        "Starting ZarinMah "
        "TGJU + Telegram + Eitaa bot..."
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
    # وضعیت ارسال
    # =====================================================

    status = load_send_status()

    telegram_sent = (
        status
        .get(
            "telegram_hourly",
            {},
        )
        .get(
            "slot"
        )
        == current_slot
    )

    eitaa_sent = (
        status
        .get(
            "eitaa_hourly",
            {},
        )
        .get(
            "slot"
        )
        == current_slot
    )

    fully_sent = (
        status
        .get(
            "hourly",
            {},
        )
        .get(
            "slot"
        )
        == current_slot
    )

    if (
        (scheduled_run or watchdog_retry)
        and fully_sent
    ):

        print(
            f"Hourly post for "
            f"{current_slot} "
            "has already been sent "
            "to all destinations."
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
    # قیمت تازه TGJU؛ در نبود نرخ تازه، نوسان
    # =====================================================

    prices = get_hourly_prices_with_fallback()

    # =====================================================
    # ساخت پیام
    # =====================================================

    message = build_message(
        prices,
        previous,
    )

    # =====================================================
    # ارسال تلگرام
    # =====================================================

    if not telegram_sent:

        print(
            "Sending price message "
            "to Telegram..."
        )

        send_to_telegram(
            message
        )

        mark_telegram_sent(
            current_slot
        )

        telegram_sent = True

        print(
            "Telegram message sent successfully."
        )

    else:

        print(
            "Telegram message for "
            f"{current_slot} already sent."
        )

    # =====================================================
    # ارسال ایتا
    # =====================================================

    if not eitaa_sent:

        send_to_eitaa(
            message
        )

        mark_eitaa_sent(
            current_slot
        )

        eitaa_sent = True

    else:

        print(
            "Eitaa message for "
            f"{current_slot} already sent."
        )

    # =====================================================
    # هر دو مقصد موفق
    # =====================================================

    if (
        telegram_sent
        and eitaa_sent
    ):

        mark_hourly_complete(
            current_slot
        )

        print(
            "Telegram + Eitaa "
            "hourly send completed."
        )

    # =====================================================
    # ذخیره قیمت
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
# شروع
# =========================================================

if __name__ == "__main__":
    main()
