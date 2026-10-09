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

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
EITAAYAR_TOKEN = os.environ.get("EITAAYAR_TOKEN", "").strip()
EITAA_CHAT_ID = os.environ.get("EITAA_CHAT_ID", "").strip().lstrip("@")
CHANNEL = "@ZarinMahGold"
TEHRAN = ZoneInfo("Asia/Tehran")
PREVIOUS_FILE = "previous_prices.json"
STATUS_FILE = "send_status.json"

# اول TGJU؛ اگر قیمت قدیمی باشد، نوسان جایگزین می‌شود.
PRICE_SOURCES = {
    "gold": {"name": "TGJU طلا", "channel": "tgjugold"},
    "currency": {"name": "TGJU ارز", "channel": "tgjucurrency"},
    "coin": {"name": "TGJU سکه", "channel": "tgjucoin"},
}

NAVASAN_CHANNEL = "navasanchannel"

# قیمت باید از پستی باشد که حداکثر ۶۰ دقیقه از انتشار آن گذشته است.
MAX_PRICE_AGE_MINUTES = 60

LAST_PRICE_META = {}
_NAVASAN_POST_CACHE = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}


# =========================================================
# پاک‌سازی و تبدیل داده‌ها
# =========================================================

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
    text = (
        text.replace("\u200c", " ")
        .replace("\u200f", " ")
        .replace("\ufeff", " ")
    )
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

    # قیمت‌های TGJU از ریال به تومان تبدیل می‌شوند.
    if unit == "rial":
        number /= 10

    return int(round(number))


def get_message_id(link):
    match = re.search(r"/(\d+)(?:\?.*)?$", link or "")
    return int(match.group(1)) if match else 0


def parse_posted_at(value):
    """زمان انتشار واقعی پست را از HTML تلگرام می‌خواند."""
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )

        # زمان بدون منطقه زمانی، قابل تأیید محسوب نمی‌شود.
        if parsed.tzinfo is None:
            return None

        return parsed.astimezone(TEHRAN)

    except (TypeError, ValueError):
        return None


def post_age_minutes(posted_at):
    if not posted_at:
        return None

    return (
        datetime.now(TEHRAN) - posted_at
    ).total_seconds() / 60


def post_is_fresh(posted_at):
    age = post_age_minutes(posted_at)

    return (
        age is not None
        and -5 <= age <= MAX_PRICE_AGE_MINUTES
    )


# =========================================================
# دریافت پست‌های کانال
# =========================================================

def fetch_channel_posts(channel, max_pages=8):
    posts = []
    seen_links = set()
    before = None

    for page_number in range(1, max_pages + 1):
        url = f"https://t.me/s/{channel}"

        if before:
            url += f"?before={before}"

        print(f"Reading @{channel}, page {page_number}...")

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

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
            link = date_node.get("href", "").strip()

            if not text or not link or link in seen_links:
                continue

            seen_links.add(link)

            time_node = wrapper.select_one("time[datetime]")
            raw_datetime = (
                time_node.get("datetime")
                if time_node
                else date_node.get("datetime")
            )
            posted_at = parse_posted_at(raw_datetime)

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

    # جدیدترین پست ابتدا بررسی می‌شود.
    posts.sort(
        key=lambda item: item["message_id"],
        reverse=True,
    )

    print(f"Total posts collected from @{channel}: {len(posts)}")

    if posts:
        print("Newest message ID:", posts[0]["message_id"])
        print("Newest message link:", posts[0]["link"])

    return posts


# =========================================================
# استخراج قیمت‌ها از قالب پست TGJU
# =========================================================

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
        r"قیمت\s*لحظه\s*ای\s*[:：]?\s*([\d,٬]+)\s*ریال",
        section,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    price = parse_number(match.group(1), "rial")

    if price is None or not minimum <= price <= maximum:
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

    match = re.search(
        r"#قیمت[_\s]*دلار\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return {}

    remaining = text[match.end():]

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
            stop_positions.append(stop.start())

    section = (
        remaining[:min(stop_positions)]
        if stop_positions
        else remaining
    )

    price = extract_instant_price(
        section,
        100_000,
        3_000_000,
    )

    return {"dollar": price} if price else {}


def parse_coin_post(text):
    text = normalize_digits(clean_text(text))

    definitions = {
        "coin": {
            "pattern": r"(?:^|\n)\s*⭕️\s*سکه\s*امامی",
            "min": 10_000_000,
            "max": 5_000_000_000,
        },
        "half": {
            "pattern": r"(?:^|\n)\s*⭕️\s*نیم\s*سکه",
            "min": 5_000_000,
            "max": 2_000_000_000,
        },
        "quarter": {
            "pattern": r"(?:^|\n)\s*⭕️\s*ربع\s*سکه",
            "min": 2_000_000,
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
# دریافت آخرین قیمت از TGJU و بررسی تازگی آن
# =========================================================

def get_latest_asset_price(channel_key, asset):
    config = PRICE_SOURCES[channel_key]
    posts = fetch_channel_posts(config["channel"])

    parser = {
        "gold": parse_gold_post,
        "currency": parse_currency_post,
        "coin": parse_coin_post,
    }[channel_key]

    # اولین قیمت معتبر از جدیدترین پست به دست می‌آید.
    for post in posts:
        parsed = parser(post["text"])

        if asset not in parsed:
            continue

        posted_at = parse_posted_at(
            post.get("posted_at")
        )
        age = post_age_minutes(posted_at)
        price = parsed[asset]

        print(
            "Latest TGJU price candidate:",
            asset,
            "|",
            post["link"],
        )
        print(
            "TGJU post time:",
            posted_at.isoformat()
            if posted_at
            else "UNKNOWN",
        )
        print(
            "TGJU post age (minutes):",
            round(age, 1)
            if age is not None
            else "UNKNOWN",
        )

        if not post_is_fresh(posted_at):
            age_text = (
                f"{round(age)} دقیقه"
                if age is not None
                else "نامشخص"
            )
            raise RuntimeError(
                f"پست TGJU برای {asset} قدیمی یا "
                f"زمان آن نامشخص است: {age_text}"
            )

        return {
            "price": price,
            "link": post["link"],
            "message_id": post["message_id"],
            "posted_at": posted_at,
            "source": "TGJU",
        }

    raise RuntimeError(
        f"قیمت معتبر {asset} در کانال "
        f"{config['channel']} پیدا نشد."
    )


# =========================================================
# قیمت جایگزین از کانال نوسان
# =========================================================

def get_navasan_posts():
    global _NAVASAN_POST_CACHE

    if _NAVASAN_POST_CACHE is None:
        _NAVASAN_POST_CACHE = fetch_channel_posts(
            NAVASAN_CHANNEL,
            max_pages=8,
        )

    return _NAVASAN_POST_CACHE


def parse_navasan_asset_price(text, asset):
    """قیمت تومانی را از خط مربوط به دارایی در پست نوسان استخراج می‌کند."""
    text = normalize_digits(clean_text(text))

    lines = [
        line.strip().replace("‌", " ")
        for line in text.splitlines()
        if line.strip()
    ]

    if asset == "gold18":
        label = re.compile(
            r"طلای?\s*(?:18|۱۸)\s*عیار(?:\s*هر\s*گرم)?",
            re.IGNORECASE,
        )
        minimum, maximum = 100_000, 500_000_000

    elif asset == "dollar":
        label = re.compile(
            r"(?:^|\s)(?:💵\s*)?دلار"
            r"(?:\s+آمریکا)?(?:\s+فروش)?"
            r"(?=\s|🇺🇸|:|：)",
            re.IGNORECASE,
        )
        minimum, maximum = 100_000, 3_000_000

    elif asset == "coin":
        label = re.compile(
            r"سکه\s*امامی",
            re.IGNORECASE,
        )
        minimum, maximum = 10_000_000, 5_000_000_000

    elif asset == "half":
        label = re.compile(
            r"نیم\s*سکه",
            re.IGNORECASE,
        )
        minimum, maximum = 5_000_000, 2_000_000_000

    elif asset == "quarter":
        label = re.compile(
            r"ربع\s*سکه",
            re.IGNORECASE,
        )
        minimum, maximum = 2_000_000, 1_000_000_000

    else:
        return None

    for line in lines:
        label_match = label.search(line)

        if not label_match:
            continue

        if asset == "dollar":
            excluded = (
                "کانادا",
                "هرات",
                "سلیمانیه",
                "توافقی",
                "دولتی",
                "نیما",
                "مرکز مبادله",
            )

            if any(word in line for word in excluded):
                continue

            # اگر قیمت خرید و فروش جداگانه باشد،
            # نرخ فروش را در اولویت قرار می‌دهیم.
            if "خرید" in line and "فروش" not in line:
                continue

        if ":" in line or "：" in line:
            value_text = re.split(
                r"[:：]",
                line,
                maxsplit=1,
            )[1]
        else:
            value_text = line[label_match.end():]

        match = re.search(
            r"(?<!\d)(\d[\d,٬ ]{2,})",
            value_text,
        )

        if not match:
            continue

        # قیمت‌های این کانال بر حسب تومان‌اند.
        price = parse_number(
            match.group(1),
            "toman",
        )

        if price and minimum <= price <= maximum:
            return price

    return None


def get_latest_navasan_asset_price(asset):
    for post in get_navasan_posts():
        price = parse_navasan_asset_price(
            post.get("text", ""),
            asset,
        )

        if price is None:
            continue

        posted_at = parse_posted_at(
            post.get("posted_at")
        )
        age = post_age_minutes(posted_at)

        print(
            "Latest Navasan price candidate:",
            asset,
            "|",
            post.get("link"),
        )
        print(
            "Navasan post time:",
            posted_at.isoformat()
            if posted_at
            else "UNKNOWN",
        )
        print(
            "Navasan post age (minutes):",
            round(age, 1)
            if age is not None
            else "UNKNOWN",
        )

        if not post_is_fresh(posted_at):
            age_text = (
                f"{round(age)} دقیقه"
                if age is not None
                else "نامشخص"
            )
            raise RuntimeError(
                f"پست نوسان برای {asset} قدیمی یا "
                f"زمان آن نامشخص است: {age_text}"
            )

        return {
            "price": price,
            "link": post.get("link", ""),
            "message_id": post.get("message_id", 0),
            "posted_at": posted_at,
            "source": "نوسان",
        }

    raise RuntimeError(
        f"قیمت معتبر {asset} در پست‌های نوسان پیدا نشد."
    )


# =========================================================
# قیمت‌ها: اول TGJU، سپس نوسان در صورت نیاز
# =========================================================

def get_official_prices():
    global LAST_PRICE_META

    asset_sources = {
        "gold18": ("gold", "طلای ۱۸ عیار"),
        "dollar": ("currency", "دلار آزاد"),
        "coin": ("coin", "سکه امامی"),
        "half": ("coin", "نیم‌سکه"),
        "quarter": ("coin", "ربع‌سکه"),
    }

    prices = {}
    metadata = {}

    for asset, (channel_key, display_name) in asset_sources.items():
        try:
            record = get_latest_asset_price(
                channel_key,
                asset,
            )
            print(
                f"Using fresh TGJU price for {display_name}."
            )

        except Exception as tgju_error:
            print(
                f"TGJU price for {display_name} is "
                f"stale/unavailable: {tgju_error}"
            )
            print(
                f"Checking Navasan for {display_name}..."
            )

            try:
                record = get_latest_navasan_asset_price(
                    asset
                )

            except Exception as navasan_error:
                raise RuntimeError(
                    f"قیمت به‌روز {display_name} از هیچ‌کدام "
                    f"از منابع دریافت نشد. "
                    f"TGJU: {tgju_error}; "
                    f"نوسان: {navasan_error}"
                ) from navasan_error

            print(
                f"Using fresh Navasan fallback for {display_name}."
            )

        prices[asset] = record["price"]

        metadata[asset] = {
            "source": record["source"],
            "link": record.get("link", ""),
            "posted_at": record.get("posted_at"),
            "message_id": record.get("message_id"),
        }

    LAST_PRICE_META = metadata

    print("================================")
    print(
        "LATEST FRESH PRICES "
        "(TGJU FIRST, NAVASAN FALLBACK):"
    )
    print(
        json.dumps(
            prices,
            ensure_ascii=False,
            indent=2,
        )
    )

    for asset, info in metadata.items():
        posted_at = info["posted_at"]

        print(
            asset,
            "->",
            info["source"],
            "|",
            posted_at.strftime("%Y-%m-%d %H:%M")
            if posted_at
            else "UNKNOWN",
            "|",
            info["link"],
        )

    return prices


def get_all_prices():
    """
    سازگاری با daily_analysis.py.
    ابتدا قیمت به‌روز TGJU و سپس در صورت نیاز نوسان.
    """
    return get_official_prices()


# =========================================================
# قیمت‌های قبلی
# =========================================================

def load_previous_prices():
    if not os.path.exists(PREVIOUS_FILE):
        return None

    try:
        with open(
            PREVIOUS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return data if isinstance(data, dict) else None

    except Exception as error:
        print(
            "Could not load previous prices:",
            error,
        )
        return None


def save_current_prices(prices):
    numeric_prices = {
        key: prices[key]
        for key in (
            "gold18",
            "dollar",
            "coin",
            "half",
            "quarter",
        )
        if key in prices
    }

    with open(
        PREVIOUS_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            numeric_prices,
            file,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# وضعیت ارسال
# =========================================================

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
        print(
            "Could not load send status:",
            error,
        )
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


def mark_telegram_sent(slot):
    status = load_send_status()
    status["telegram_hourly"] = {
        "slot": slot,
        "sent_at": datetime.now(
            TEHRAN
        ).isoformat(),
    }
    save_send_status(status)


def mark_eitaa_sent(slot):
    status = load_send_status()
    status["eitaa_hourly"] = {
        "slot": slot,
        "sent_at": datetime.now(
            TEHRAN
        ).isoformat(),
    }
    save_send_status(status)


def mark_hourly_complete(slot):
    status = load_send_status()
    status["hourly"] = {
        "slot": slot,
        "sent_at": datetime.now(
            TEHRAN
        ).isoformat(),
    }
    save_send_status(status)


# =========================================================
# متن تغییر قیمت و اطلاعات منبع
# =========================================================

def change_text(current, previous):
    if previous is None:
        return "🆕 اولین ثبت"

    try:
        difference = int(current) - int(previous)
    except (ValueError, TypeError):
        return "⚪ تغییر قابل محاسبه نیست"

    if difference > 0:
        return f"🟢 ▲ +{difference:,} تومان"

    if difference < 0:
        return f"🔴 ▼ {difference:,} تومان"

    return "⚪ ➖ بدون تغییر"


def source_info(asset):
    info = LAST_PRICE_META.get(asset, {})
    source = info.get("source", "منبع نامشخص")
    posted_at = info.get("posted_at")

    time_text = (
        posted_at.astimezone(TEHRAN).strftime("%H:%M")
        if posted_at
        else "نامشخص"
    )

    return f"📡 منبع: {source} | زمان پست: {time_text}"


# =========================================================
# ساخت پیام قیمت
# =========================================================

def build_message(prices, previous):
    previous = previous or {}
    update_time = datetime.now(TEHRAN).strftime("%H:%M")

    return f"""🌙✨ زرین ماه
💎 قیمت‌های به‌روز از آخرین پست منابع

━━━━━━━━━━━━━━━━━━

🟡 طلای ۱۸ عیار
💰 {prices["gold18"]:,} تومان
{change_text(prices["gold18"], previous.get("gold18"))}
{source_info("gold18")}

🪙 سکه امامی
💰 {prices["coin"]:,} تومان
{change_text(prices["coin"], previous.get("coin"))}
{source_info("coin")}

🪙 نیم‌سکه
💰 {prices["half"]:,} تومان
{change_text(prices["half"], previous.get("half"))}
{source_info("half")}

🪙 ربع‌سکه
💰 {prices["quarter"]:,} تومان
{change_text(prices["quarter"], previous.get("quarter"))}
{source_info("quarter")}

💵 دلار آزاد
💰 {prices["dollar"]:,} تومان
{change_text(prices["dollar"], previous.get("dollar"))}
{source_info("dollar")}

━━━━━━━━━━━━━━━━━━

🕒 زمان بررسی ربات: {update_time}
📊 اولویت منبع: TGJU؛ در صورت قدیمی بودن، نوسان

🔸 TGJU طلا: https://t.me/tgjugold
🔸 TGJU سکه: https://t.me/tgjucoin
🔸 TGJU ارز: https://t.me/tgjucurrency
🔸 نوسان (منبع جایگزین): https://t.me/navasanchannel

━━━━━━━━━━━━━━━━━━

🌙 زرین ماه
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""


# =========================================================
# ارسال به تلگرام
# =========================================================

def send_to_telegram(message):
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    url = (
        f"https://api.telegram.org/"
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

    response.raise_for_status()
    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result}"
        )

    return result


# =========================================================
# ارسال به ایتا
# =========================================================

def send_to_eitaa(message):
    if not EITAAYAR_TOKEN:
        raise RuntimeError(
            "EITAAYAR_TOKEN تنظیم نشده است."
        )

    if not EITAA_CHAT_ID:
        raise RuntimeError(
            "EITAA_CHAT_ID تنظیم نشده است."
        )

    url = (
        f"https://eitaayar.ir/api/"
        f"{EITAAYAR_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": EITAA_CHAT_ID,
            "text": message,
        },
        timeout=30,
    )

    print(
        "Eitaa HTTP status:",
        response.status_code,
    )
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

    return result


# =========================================================
# اجرای اصلی
# =========================================================

def main():
    print("=================================")
    print(
        "Starting ZarinMah "
        "TGJU -> Navasan price bot..."
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

    # خاموشی زمان‌بندی‌شده از ۲۲:۰۰ تا ۰۸:۵۹ به وقت تهران
    if scheduled_run or watchdog_retry:
        if now.hour >= 22 or now.hour < 9:
            print(
                "Price bot disabled between "
                "22:00 and 08:59 Tehran time."
            )
            return

    status = load_send_status()

    telegram_sent = (
        status.get("telegram_hourly", {}).get("slot")
        == current_slot
    )
    eitaa_sent = (
        status.get("eitaa_hourly", {}).get("slot")
        == current_slot
    )
    fully_sent = (
        status.get("hourly", {}).get("slot")
        == current_slot
    )

    if (scheduled_run or watchdog_retry) and fully_sent:
        print(
            f"Hourly post for {current_slot} "
            "already sent to all destinations; skipping."
        )
        return

    previous = load_previous_prices()

    # برای هر دارایی اول TGJU بررسی می‌شود.
    # اگر قدیمی/نامعتبر باشد، نوسان جایگزین می‌شود.
    prices = get_official_prices()

    message = build_message(
        prices,
        previous,
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
    print("Verified prices saved.")
    print("Bot completed successfully.")


if __name__ == "__main__":
    main()
