import os
import re
import json
import html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# ================================ تنظیمات ================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
EITAAYAR_TOKEN = os.environ.get("EITAAYAR_TOKEN", "").strip()
EITAA_CHAT_ID = os.environ.get("EITAA_CHAT_ID", "").strip().lstrip("@")

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

# منابع اصلی قیمت
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

# منبع جایگزین
FALLBACK_SOURCE = {
    "name": "نوسان",
    "channel": "navasanchannel",
}

# اگر پست قیمت بیش از این مدت قدیمی باشد، استفاده نمی‌شود.
MAX_PRICE_AGE_MINUTES = 45

# جلوگیری از دریافت چندباره یک کانال در یک اجرای ربات
CHANNEL_POST_CACHE = {}


# ================================ پاکسازی و اعداد ================================

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
    text = text.replace("\u200c", " ")
    text = text.replace("\u200f", " ")
    text = text.replace("\ufeff", " ")
    text = text.replace("٬", ",")
    text = text.replace("،", ",")

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
    match = re.search(r"/(\d+)(?:\?.*)?$", link or "")
    return int(match.group(1)) if match else 0


# ================================ بررسی تاریخ پست ================================

def parse_posted_at(date_node):
    if not date_node:
        return None

    time_node = date_node.select_one("time[datetime]")
    raw = time_node.get("datetime", "") if time_node else ""
    raw = raw or date_node.get("datetime", "")

    if not raw:
        return None

    try:
        parsed = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=TEHRAN)

        return parsed.astimezone(TEHRAN)

    except (ValueError, TypeError):
        return None


def post_age_minutes(post):
    raw = post.get("posted_at")

    if not raw:
        return None

    try:
        posted_at = datetime.fromisoformat(
            str(raw).replace("Z", "+00:00")
        )

        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=TEHRAN)

        age = (
            datetime.now(TEHRAN)
            - posted_at.astimezone(TEHRAN)
        ).total_seconds() / 60

        return age

    except (ValueError, TypeError):
        return None


def is_fresh_price_post(post):
    age = post_age_minutes(post)

    return (
        age is not None
        and -5 <= age <= MAX_PRICE_AGE_MINUTES
    )


# ================================ دریافت پست‌های تلگرام ================================

def fetch_channel_posts(channel, max_pages=8):
    cached = CHANNEL_POST_CACHE.get(channel)

    if cached and cached["max_pages"] >= max_pages:
        return list(cached["posts"])

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
                text_node.get_text("\n", strip=True)
            )

            link = date_node.get("href", "")

            if not text or not link or link in seen_links:
                continue

            seen_links.add(link)

            posted_at = parse_posted_at(date_node)

            page_posts.append({
                "text": text,
                "link": link,
                "message_id": get_message_id(link),
                "posted_at": (
                    posted_at.isoformat()
                    if posted_at
                    else None
                ),
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

    print(f"Total posts collected from {channel}: {len(posts)}")

    if posts:
        print(
            "Newest message:",
            posts[0]["link"],
            "|",
            posts[0].get("posted_at"),
        )

    CHANNEL_POST_CACHE[channel] = {
        "max_pages": max_pages,
        "posts": list(posts),
    }

    return posts


# ================================ پارسر TGJU ================================

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

    price = parse_number(
        match.group(1),
        "rial",
    )

    if not price or not minimum <= price <= maximum:
        return None

    return price


def parse_gold_post(text):
    patterns = [
        r"(?:^|\n)\s*⭕️\s*قیمت\s*طلای\s*(?:18|۱۸)\s*عیار",
        r"(?:^|\n)\s*⭕️\s*طلای\s*(?:18|۱۸)\s*عیار",
        r"(?:^|\n)\s*قیمت\s*طلای\s*(?:18|۱۸)\s*عیار",
    ]

    for pattern in patterns:

        section = get_asset_section(text, pattern)

        price = extract_instant_price(
            section,
            100_000,
            500_000_000,
        )

        if price:
            return {"gold18": price}

    return {}


def parse_currency_post(text):
    text = normalize_digits(clean_text(text))

    dollar_match = re.search(
        r"#قیمت[_\s]*دلار\b",
        text,
        flags=re.IGNORECASE,
    )

    if not dollar_match:
        return {}

    remaining = text[dollar_match.end():]

    stop_patterns = [
        r"#قیمت[_\s]*دلار[_\s]*توافقی",
        r"#قیمت[_\s]*دلار[_\s]*سلیمانیه",
        r"#قیمت[_\s]*دلار[_\s]*هرات",
        r"#قیمت[_\s]*دلار[_\s]*سنا",
        r"#قیمت[_\s]*دلار[_\s]*نیما",
        r"⭕️\s*قیمت\s*دلار\s*دولتی",
    ]

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
    text = normalize_digits(clean_text(text))

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

    for asset, (
        pattern,
        minimum,
        maximum,
    ) in definitions.items():

        section = get_asset_section(text, pattern)

        price = extract_instant_price(
            section,
            minimum,
            maximum,
        )

        if price:
            result[asset] = price

    return result


# ================================ پارسر نوسان ================================

def parse_navasan_post(text):
    """
    قیمت‌های تومانی کانال @navasanchannel
    را استخراج می‌کند.
    """

    text = normalize_digits(clean_text(text))

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    result = {}

    def find_line_price(
        label_pattern,
        minimum,
        maximum,
        require_sell=False,
    ):
        for line in lines:

            if not re.search(
                label_pattern,
                line,
                flags=re.IGNORECASE,
            ):
                continue

            if require_sell and "فروش" not in line:
                continue

            match = re.search(
                label_pattern + r"[^\d\n]*([\d,]+)",
                line,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            price = parse_number(
                match.group(1),
                "toman",
            )

            if price and minimum <= price <= maximum:
                return price

        return None

    # اگر هم خرید و هم فروش وجود داشته باشد،
    # نرخ فروش دلار اولویت دارد.
    dollar = find_line_price(
        r"دلار\s*آمریکا",
        10_000,
        10_000_000,
        require_sell=True,
    )

    # بعضی پست‌ها نرخ دلار را بدون کلمه «فروش» درج می‌کنند.
    if dollar is None:
        dollar = find_line_price(
            r"دلار\s*آمریکا",
            10_000,
            10_000_000,
        )

    if dollar is not None:
        result["dollar"] = dollar

    fields = {
        "gold18": (
            r"طلای\s*(?:18|۱۸)\s*عیار",
            1_000_000,
            500_000_000,
        ),
        "coin": (
            r"سکه\s*امامی",
            20_000_000,
            5_000_000_000,
        ),
        "half": (
            r"نیم\s*سکه",
            10_000_000,
            2_000_000_000,
        ),
        "quarter": (
            r"ربع\s*سکه",
            5_000_000,
            1_000_000_000,
        ),
    }

    for asset, (
        pattern,
        minimum,
        maximum,
    ) in fields.items():

        price = find_line_price(
            pattern,
            minimum,
            maximum,
        )

        if price is not None:
            result[asset] = price

    return result


# ================================ انتخاب منبع تازه ================================

def get_primary_parser(channel_key):
    return {
        "gold": parse_gold_post,
        "currency": parse_currency_post,
        "coin": parse_coin_post,
    }[channel_key]


def find_recent_price(
    posts,
    parser,
    asset,
    source_name,
    source_channel,
):
    # اولین پست دارای قیمت، جدیدترین پست مرتبط است.
    # اگر همان پست قدیمی باشد، به پست قدیمی‌تری برنمی‌گردیم.

    for post in posts:

        try:
            parsed = parser(post["text"])
        except Exception as error:
            print("Price parser error:", error)
            continue

        if asset not in parsed:
            continue

        age = post_age_minutes(post)

        if not is_fresh_price_post(post):
            print(
                f"STALE PRICE POST: {source_name} | "
                f"{asset} | age={age} minutes | "
                f"{post.get('link', '')}"
            )
            return None

        return {
            "price": parsed[asset],
            "link": post.get("link", ""),
            "message_id": post.get("message_id"),
            "posted_at": post.get("posted_at"),
            "age_minutes": age,
            "source_name": source_name,
            "source_channel": source_channel,
        }

    return None


def get_latest_asset_price(channel_key, asset):
    config = PRICE_SOURCES[channel_key]
    parser = get_primary_parser(channel_key)

    primary_record = None

    # مرحله اول: تلاش برای گرفتن قیمت تازه از TGJU
    try:
        primary_posts = fetch_channel_posts(
            config["channel"]
        )

        primary_record = find_recent_price(
            primary_posts,
            parser,
            asset,
            config["name"],
            config["channel"],
        )

    except Exception as error:
        print(
            f"Primary source error "
            f"({config['channel']}) for {asset}: {error}"
        )

    if primary_record:
        print(
            f"PRICE SELECTED: {asset}="
            f"{primary_record['price']:,} toman | "
            f"source={primary_record['source_name']} | "
            f"age={primary_record['age_minutes']:.1f}m"
        )

        return primary_record

    # مرحله دوم: TGJU قیمت تازه ندارد؛ نوسان بررسی می‌شود.
    print(
        f"No fresh {asset} price from "
        f"{config['channel']}; trying "
        f"@{FALLBACK_SOURCE['channel']}..."
    )

    try:
        fallback_posts = fetch_channel_posts(
            FALLBACK_SOURCE["channel"],
            max_pages=3,
        )

        fallback_record = find_recent_price(
            fallback_posts,
            parse_navasan_post,
            asset,
            FALLBACK_SOURCE["name"],
            FALLBACK_SOURCE["channel"],
        )

    except Exception as error:
        print(
            f"Fallback source error "
            f"({FALLBACK_SOURCE['channel']}) "
            f"for {asset}: {error}"
        )

        fallback_record = None

    if fallback_record:
        print(
            f"FALLBACK SELECTED: {asset}="
            f"{fallback_record['price']:,} toman | "
            f"source={fallback_record['source_name']} | "
            f"age={fallback_record['age_minutes']:.1f}m | "
            f"link={fallback_record['link']}"
        )

        return fallback_record

    # هیچ قیمت تازه‌ای پیدا نشده است؛ قیمت قدیمی منتشر نکن.
    raise RuntimeError(
        f"قیمت تازه برای {asset} پیدا نشد؛ "
        f"نه در {config['channel']} و نه در "
        f"@{FALLBACK_SOURCE['channel']}. "
        "برای جلوگیری از انتشار قیمت قدیمی، ارسال متوقف شد."
    )


def get_official_prices(with_sources=False):
    prices = {}
    sources = {}

    jobs = [
        ("gold", "gold18"),
        ("currency", "dollar"),
        ("coin", "coin"),
        ("coin", "half"),
        ("coin", "quarter"),
    ]

    for channel_key, asset in jobs:

        record = get_latest_asset_price(
            channel_key,
            asset,
        )

        prices[asset] = record["price"]
        sources[asset] = record

    print("FRESH MARKET PRICES:")
    print(
        json.dumps(
            prices,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("SOURCE DETAILS:")
    print(
        json.dumps(
            {
                asset: {
                    "source": item.get("source_name"),
                    "posted_at": item.get("posted_at"),
                    "age_minutes": item.get("age_minutes"),
                    "link": item.get("link"),
                }
                for asset, item in sources.items()
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if with_sources:
        return prices, sources

    return prices


# سازگاری با daily_analysis.py
def get_all_prices():
    return get_official_prices()


# ================================ ذخیره قیمت ================================

def load_previous_prices():
    if not os.path.exists(PREVIOUS_FILE):
        return None

    try:
        with open(
            PREVIOUS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except Exception as error:
        print("Could not load previous prices:", error)
        return None


def save_current_prices(prices):
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


# ================================ وضعیت ارسال ================================

def load_send_status():
    if not os.path.exists(STATUS_FILE):
        return {}

    try:
        with open(
            STATUS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return data if isinstance(data, dict) else {}

    except Exception as error:
        print("Could not load send status:", error)
        return {}


def save_send_status(status):
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


def mark_destination_sent(key, slot):
    status = load_send_status()

    status[key] = {
        "slot": slot,
        "sent_at": datetime.now(TEHRAN).isoformat(),
    }

    save_send_status(status)


def mark_telegram_sent(slot):
    mark_destination_sent("telegram_hourly", slot)


def mark_eitaa_sent(slot):
    mark_destination_sent("eitaa_hourly", slot)


def mark_hourly_complete(slot):
    mark_destination_sent("hourly", slot)


# ================================ ساخت پیام ================================

def change_text(current, previous):
    if previous is None:
        return "🆕 اولین ثبت"

    difference = current - previous

    if difference > 0:
        return f"🟢 ▲ +{difference:,} تومان"

    if difference < 0:
        return f"🔴 ▼ {difference:,} تومان"

    return "⚪ ➖ بدون تغییر"


def source_description(asset, sources):
    info = (sources or {}).get(asset, {})
    name = info.get("source_name", "منبع قیمت")
    raw_time = info.get("posted_at")

    if raw_time:
        try:
            posted_at = datetime.fromisoformat(
                str(raw_time).replace("Z", "+00:00")
            )

            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=TEHRAN)

            time_text = posted_at.astimezone(
                TEHRAN
            ).strftime("%H:%M")

            return f"📍 منبع: {name} | زمان پست: {time_text}"

        except (ValueError, TypeError):
            pass

    return f"📍 منبع: {name}"


def build_message(
    prices,
    previous,
    price_sources=None,
):
    previous = previous or {}

    update_time = datetime.now(
        TEHRAN
    ).strftime("%H:%M")

    return f"""🌙✨ زرین ماه
💎 آخرین قیمت‌های تازه بازار

━━━━━━━━━━━━━━━━━━

🟡 طلای ۱۸ عیار
💰 {prices['gold18']:,} تومان
{change_text(prices['gold18'], previous.get('gold18'))}
{source_description('gold18', price_sources)}

🪙 سکه امامی
💰 {prices['coin']:,} تومان
{change_text(prices['coin'], previous.get('coin'))}
{source_description('coin', price_sources)}

🪙 نیم‌سکه
💰 {prices['half']:,} تومان
{change_text(prices['half'], previous.get('half'))}
{source_description('half', price_sources)}

🪙 ربع‌سکه
💰 {prices['quarter']:,} تومان
{change_text(prices['quarter'], previous.get('quarter'))}
{source_description('quarter', price_sources)}

💵 دلار آزاد
💰 {prices['dollar']:,} تومان
{change_text(prices['dollar'], previous.get('dollar'))}
{source_description('dollar', price_sources)}

━━━━━━━━━━━━━━━━━━

🕒 زمان تهیه گزارش: {update_time}
⏱ فقط پست‌های قیمتی با قدمت حداکثر {MAX_PRICE_AGE_MINUTES} دقیقه استفاده می‌شوند.

🔗 کانال‌های TGJU:
▫️ طلا: https://t.me/tgjugold
▫️ سکه: https://t.me/tgjucoin
▫️ ارز: https://t.me/tgjucurrency
🔗 منبع جایگزین نوسان: https://t.me/navasanchannel

━━━━━━━━━━━━━━━━━━

🌙 زرین ماه
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""


# ================================ ارسال تلگرام ================================

def send_to_telegram(message):
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHANNEL,
            "text": message,
        },
        timeout=30,
    )

    print("Telegram HTTP status:", response.status_code)
    print("Telegram response:", response.text)

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result}"
        )

    return result


# ================================ ارسال ایتا ================================

def send_to_eitaa(message):
    if not EITAAYAR_TOKEN:
        raise RuntimeError(
            "EITAAYAR_TOKEN تنظیم نشده است."
        )

    if not EITAA_CHAT_ID:
        raise RuntimeError(
            "EITAA_CHAT_ID تنظیم نشده است."
        )

    response = requests.post(
        f"https://eitaayar.ir/api/{EITAAYAR_TOKEN}/sendMessage",
        data={
            "chat_id": EITAA_CHAT_ID,
            "text": message,
        },
        timeout=30,
    )

    print("Eitaa HTTP status:", response.status_code)
    print("Eitaa response:", response.text)

    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as error:
        raise RuntimeError(
            "Eitaa API پاسخ JSON معتبر برنگرداند."
        ) from error

    if not result.get("ok"):
        raise RuntimeError(
            f"Eitaa API error: {result}"
        )

    print("Eitaa message sent successfully.")

    return result


# ================================ اجرای اصلی ================================

def main():
    print("=================================")
    print(
        "Starting ZarinMah Price Bot: "
        "TGJU + Navasan + Telegram + Eitaa"
    )
    print("=================================")

    scheduled_run = (
        os.environ.get("SCHEDULED_RUN") == "true"
    )

    watchdog_retry = (
        os.environ.get("WATCHDOG_RETRY") == "true"
    )

    now = datetime.now(TEHRAN)

    print(
        "Tehran time:",
        now.strftime("%Y-%m-%d %H:%M:%S"),
    )

    current_slot = now.strftime("%Y-%m-%d %H")

    # خاموشی ربات قیمت از ساعت ۲۲ تا ۸:۵۹
    if (
        scheduled_run or watchdog_retry
    ) and (
        now.hour >= 22 or now.hour < 9
    ):
        print(
            "Price bot is disabled "
            "between 22:00 and 08:59 Tehran time."
        )
        return

    status = load_send_status()

    telegram_sent = (
        status.get(
            "telegram_hourly",
            {},
        ).get("slot")
        == current_slot
    )

    eitaa_sent = (
        status.get(
            "eitaa_hourly",
            {},
        ).get("slot")
        == current_slot
    )

    fully_sent = (
        status.get(
            "hourly",
            {},
        ).get("slot")
        == current_slot
    )

    if (
        scheduled_run or watchdog_retry
    ) and fully_sent:
        print(
            f"Hourly post for {current_slot} "
            "was already sent to both destinations; skipping."
        )
        return

    previous = load_previous_prices()

    # اگر قیمت TGJU قدیمی باشد، قیمت تازه نوسان جایگزین می‌شود.
    # اگر هیچ منبعی قیمت تازه نداشته باشد، ارسال متوقف می‌شود.
    prices, price_sources = get_official_prices(
        with_sources=True
    )

    message = build_message(
        prices,
        previous,
        price_sources,
    )

    if not telegram_sent:
        print("Sending price message to Telegram...")

        send_to_telegram(message)
        mark_telegram_sent(current_slot)

        telegram_sent = True

        print("Telegram message sent successfully.")

    else:
        print(
            f"Telegram message for {current_slot} "
            "already sent; skipping."
        )

    if not eitaa_sent:
        print("Sending price message to Eitaa...")

        send_to_eitaa(message)
        mark_eitaa_sent(current_slot)

        eitaa_sent = True

        print("Eitaa message sent successfully.")

    else:
        print(
            f"Eitaa message for {current_slot} "
            "already sent; skipping."
        )

    if telegram_sent and eitaa_sent:
        mark_hourly_complete(current_slot)
        print("Telegram + Eitaa hourly send completed.")

    save_current_prices(prices)

    print("Verified fresh prices saved.")
    print("Bot completed successfully.")


if __name__ == "__main__":
    main()
