import html
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

# =========================================================
# تنظیمات اصلی
# =========================================================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
EITAAYAR_TOKEN = os.environ.get("EITAAYAR_TOKEN", "").strip()
EITAA_CHAT_ID = os.environ.get("EITAA_CHAT_ID", "").strip()
CHANNEL = "@ZarinMahGold"
TEHRAN = ZoneInfo("Asia/Tehran")
PREVIOUS_FILE = "previous_prices.json"
STATUS_FILE = "send_status.json"

# منبع اصلی قیمت
PRICE_SOURCES = {
    "gold": {"name": "TGJU طلا", "channel": "tgjugold"},
    "currency": {"name": "TGJU ارز", "channel": "tgjucurrency"},
    "coin": {"name": "TGJU سکه", "channel": "tgjucoin"},
}

# منبع جایگزین: کانال نوسان
NAVASAN_CHANNEL = "navasanchannel"
NAVASAN_URL = "https://t.me/navasanchannel"

# اگر نرخ TGJU بیشتر از ۲ ساعت قدیمی باشد، از نوسان استفاده می‌شود.
MAX_PRIMARY_PRICE_AGE_MINUTES = 120

# نرخ نوسان باید حداکثر ۶ ساعت عمر داشته باشد.
MAX_NAVASAN_PRICE_AGE_MINUTES = 360

PRICE_SOURCE_USED = "TGJU"
PRICE_SOURCE_REASON = ""

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}


# =========================================================
# ابزارهای متن، عدد و پیام تلگرام
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


def get_post_age_minutes(post):
    raw = post.get("published_at")
    if not raw:
        return None
    try:
        published = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if published.tzinfo is None:
            published = published.replace(tzinfo=TEHRAN)
        published = published.astimezone(TEHRAN)
        return (datetime.now(TEHRAN) - published).total_seconds() / 60
    except (TypeError, ValueError, OverflowError):
        return None


# =========================================================
# خواندن پست‌های عمومی کانال تلگرام
# =========================================================
def fetch_channel_posts(channel, max_pages=8):
    posts = []
    seen_links = set()
    before = None

    for page_number in range(1, max_pages + 1):
        url = f"https://t.me/s/{channel}"
        if before:
            url += f"?before={before}"

        print(f"Reading {channel} page {page_number}...")
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        wrappers = soup.select("div.tgme_widget_message_wrap")
        if not wrappers:
            break

        page_posts = []
        for wrapper in wrappers:
            text_node = wrapper.select_one("div.tgme_widget_message_text")
            date_node = wrapper.select_one("a.tgme_widget_message_date")
            if not text_node or not date_node:
                continue

            text = clean_text(text_node.get_text("\n", strip=True))
            link = date_node.get("href", "")
            time_node = date_node.select_one("time[datetime]")
            published_at = time_node.get("datetime") if time_node else None

            if not text or not link or link in seen_links:
                continue
            seen_links.add(link)
            page_posts.append({
                "text": text,
                "link": link,
                "message_id": get_message_id(link),
                "published_at": published_at,
            })

        print("Posts found on page:", len(page_posts))
        if not page_posts:
            break
        posts.extend(page_posts)

        ids = [post["message_id"] for post in page_posts if post["message_id"] > 0]
        if not ids:
            break
        before = str(min(ids))

    posts.sort(key=lambda item: item["message_id"], reverse=True)
    print(f"Total posts collected from {channel}: {len(posts)}")
    if posts:
        print("Newest message ID:", posts[0]["message_id"])
        print("Newest message link:", posts[0]["link"])
    return posts


# =========================================================
# استخراج قیمت از پست‌های TGJU
# =========================================================
def get_asset_section(text, asset_pattern):
    text = normalize_digits(clean_text(text))
    match = re.search(asset_pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    remaining = text[match.end():]
    next_section = re.search(r"(?:^|\n)\s*⭕️", remaining)
    return remaining[:next_section.start()] if next_section else remaining


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
    patterns = [
        r"(?:^|\n)\s*⭕️\s*قیمت\s*طلای\s*(?:18|۱۸)\s*عیار",
        r"(?:^|\n)\s*⭕️\s*طلای\s*(?:18|۱۸)\s*عیار",
        r"(?:^|\n)\s*قیمت\s*طلای\s*(?:18|۱۸)\s*عیار",
    ]
    for pattern in patterns:
        section = get_asset_section(text, pattern)
        price = extract_instant_price(section, 100_000, 500_000_000)
        if price:
            return {"gold18": price}
    return {}


def parse_currency_post(text):
    text = normalize_digits(clean_text(text))
    dollar_match = re.search(r"#قیمت[_\s]*دلار\b", text, flags=re.IGNORECASE)
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
    stops = [
        match.start()
        for pattern in stop_patterns
        if (match := re.search(pattern, remaining, flags=re.IGNORECASE))
    ]
    section = remaining[:min(stops)] if stops else remaining
    price = extract_instant_price(section, 100_000, 1_000_000)
    return {"dollar": price} if price else {}


def parse_coin_post(text):
    text = normalize_digits(clean_text(text))
    definitions = {
        "coin": (r"(?:^|\n)\s*⭕️\s*سکه\s*امامی", 100_000_000, 5_000_000_000),
        "half": (r"(?:^|\n)\s*⭕️\s*نیم\s*سکه", 50_000_000, 2_000_000_000),
        "quarter": (r"(?:^|\n)\s*⭕️\s*ربع\s*سکه", 20_000_000, 1_000_000_000),
    }
    result = {}
    for asset, (pattern, minimum, maximum) in definitions.items():
        section = get_asset_section(text, pattern)
        price = extract_instant_price(section, minimum, maximum)
        if price:
            result[asset] = price
    return result


def get_latest_asset_price(channel_key, asset):
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

        age = get_post_age_minutes(post)
        if age is None:
            raise RuntimeError(
                f"زمان انتشار نرخ {asset} در {config['channel']} قابل بررسی نیست."
            )
        if age < -10 or age > MAX_PRIMARY_PRICE_AGE_MINUTES:
            raise RuntimeError(
                f"آخرین نرخ {asset} در {config['channel']} قدیمی است "
                f"(سن پست: {age:.0f} دقیقه)."
            )

        price = parsed[asset]
        print("LATEST FRESH TGJU MATCH")
        print("Source:", config["name"])
        print("Message ID:", post["message_id"])
        print("Message link:", post["link"])
        print("Asset:", asset)
        print("Instant price:", f"{price:,}", "toman")
        print("Post age (minutes):", round(age, 1))
        return {
            "price": price,
            "link": post["link"],
            "message_id": post["message_id"],
            "published_at": post.get("published_at"),
        }

    raise RuntimeError(f"قیمت تازهٔ {asset} در کانال {config['channel']} پیدا نشد.")


# =========================================================
# استخراج قیمت از کانال نوسان
# =========================================================
def parse_navasan_post(text):
    """قیمت‌های تومانی را از قالب پست‌های کانال نوسان استخراج می‌کند."""
    text = normalize_digits(clean_text(text))
    found = {}
    patterns = {
        "dollar": r"^\s*دلار\s*آمریکا\b.*?(\d[\d,]{3,})",
        "gold18": (
            r"^\s*(?:طلای\s*(?:18|۱۸)\s*عیار\b|"
            r"هر\s*گرم\s*طلای\s*(?:18|۱۸)\s*عیار\b)"
            r".*?(\d[\d,]{5,})"
        ),
        "coin": r"^\s*سکه\s*امامی\b.*?(\d[\d,]{6,})",
        "half": r"^\s*نیم\s*سکه\b.*?(\d[\d,]{6,})",
        "quarter": r"^\s*ربع\s*سکه\b.*?(\d[\d,]{6,})",
    }
    limits = {
        "dollar": (10_000, 5_000_000),
        "gold18": (1_000_000, 500_000_000),
        "coin": (100_000_000, 5_000_000_000),
        "half": (50_000_000, 2_000_000_000),
        "quarter": (20_000_000, 1_000_000_000),
    }

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for asset, pattern in patterns.items():
            if asset in found:
                continue
            match = re.search(pattern, line, flags=re.IGNORECASE)
            if not match:
                continue
            price = parse_number(match.group(1), "toman")
            if price is None:
                continue
            minimum, maximum = limits[asset]
            if minimum <= price <= maximum:
                found[asset] = price
    return found


def get_navasan_prices():
    """جدیدترین قیمت هر دارایی را از چند پست تازهٔ کانال نوسان جمع می‌کند."""
    print("Fetching fallback prices from Navasan...")
    posts = fetch_channel_posts(NAVASAN_CHANNEL, max_pages=4)
    required_assets = ("gold18", "dollar", "coin", "half", "quarter")
    result = {}
    asset_post = {}

    for post in posts:  # پست‌ها از جدیدترین به قدیمی‌ترین مرتب شده‌اند.
        parsed = parse_navasan_post(post.get("text", ""))
        if not parsed:
            continue
        age = get_post_age_minutes(post)
        if age is not None and (
            age < -10 or age > MAX_NAVASAN_PRICE_AGE_MINUTES
        ):
            continue
        for asset, price in parsed.items():
            if asset not in result:
                result[asset] = price
                asset_post[asset] = post.get("link", "")
        if all(asset in result for asset in required_assets):
            break

    missing = [asset for asset in required_assets if asset not in result]
    if missing:
        raise RuntimeError(
            "قیمت‌های کافی از کانال نوسان دریافت نشد. دارایی‌های ناموجود: "
            + ", ".join(missing)
        )

    print("Navasan fallback prices:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    for asset, link in asset_post.items():
        print(f"Navasan {asset} source: {link}")
    return result


# =========================================================
# انتخاب منبع قیمت: جمعه نوسان، روزهای دیگر ابتدا TGJU
# =========================================================
def get_official_prices():
    global PRICE_SOURCE_USED, PRICE_SOURCE_REASON
    now = datetime.now(TEHRAN)

    # در پایتون، جمعه برابر با weekday() == 4 است.
    if now.weekday() == 4:
        print("Friday detected: using Navasan as the price source.")
        PRICE_SOURCE_USED = "Navasan"
        PRICE_SOURCE_REASON = "روز جمعه؛ منبع جایگزین"
        return get_navasan_prices()

    try:
        result = {}
        result["gold18"] = get_latest_asset_price("gold", "gold18")["price"]
        result["dollar"] = get_latest_asset_price("currency", "dollar")["price"]
        result["coin"] = get_latest_asset_price("coin", "coin")["price"]
        result["half"] = get_latest_asset_price("coin", "half")["price"]
        result["quarter"] = get_latest_asset_price("coin", "quarter")["price"]

        PRICE_SOURCE_USED = "TGJU"
        PRICE_SOURCE_REASON = ""
        print("LATEST FRESH TGJU INSTANT PRICES:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    except Exception as error:
        print("TGJU rates unavailable or too old:", error)
        print("Switching all prices to Navasan to keep the post consistent.")
        fallback_prices = get_navasan_prices()
        PRICE_SOURCE_USED = "Navasan"
        PRICE_SOURCE_REASON = "نرخ تازه در منبع اصلی پیدا نشد"
        return fallback_prices


def get_all_prices():
    """برای سازگاری با daily_analysis.py نیز از منطق اصلی و جایگزین استفاده می‌کند."""
    return get_official_prices()


# =========================================================
# ذخیرهٔ قیمت‌های قبلی برای محاسبه تغییرات
# =========================================================
def load_previous_prices():
    if not os.path.exists(PREVIOUS_FILE):
        return None
    try:
        with open(PREVIOUS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as error:
        print("Could not load previous prices:", error)
        return None


def save_current_prices(prices):
    saved_prices = dict(prices)
    saved_prices["_source"] = PRICE_SOURCE_USED
    with open(PREVIOUS_FILE, "w", encoding="utf-8") as file:
        json.dump(saved_prices, file, ensure_ascii=False, indent=2)


# =========================================================
# وضعیت ارسال در تلگرام و ایتا
# =========================================================
def load_send_status():
    if not os.path.exists(STATUS_FILE):
        return {}
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except Exception as error:
        print("Could not load send status:", error)
        return {}


def save_send_status(status):
    with open(STATUS_FILE, "w", encoding="utf-8") as file:
        json.dump(status, file, ensure_ascii=False, indent=2)


def mark_telegram_sent(slot):
    status = load_send_status()
    status["telegram_hourly"] = {
        "slot": slot,
        "sent_at": datetime.now(TEHRAN).isoformat(),
    }
    save_send_status(status)


def mark_eitaa_sent(slot):
    status = load_send_status()
    status["eitaa_hourly"] = {
        "slot": slot,
        "sent_at": datetime.now(TEHRAN).isoformat(),
    }
    save_send_status(status)


def mark_hourly_complete(slot):
    status = load_send_status()
    status["hourly"] = {
        "slot": slot,
        "sent_at": datetime.now(TEHRAN).isoformat(),
    }
    save_send_status(status)


# =========================================================
# تغییر قیمت نسبت به ثبت قبلی
# =========================================================
def change_text(current, previous):
    if previous is None:
        return "🆕 اولین ثبت"
    difference = current - previous
    if difference > 0:
        return f"🟢 ▲ +{difference:,} تومان"
    if difference < 0:
        return f"🔴 ▼ {difference:,} تومان"
    return "⚪ ➖ بدون تغییر"


# =========================================================
# ساخت پست قیمت
# =========================================================
def build_message(prices, previous):
    previous = previous or {}
    update_time = datetime.now(TEHRAN).strftime("%H:%M")
    source_header = (
        "💎 آخرین قیمت لحظه‌ای رسمی TGJU"
        if PRICE_SOURCE_USED == "TGJU"
        else "💎 قیمت لحظه‌ای از منبع جایگزین نوسان"
    )

    previous_source = previous.get("_source")
    source_changed = bool(previous) and (
        not previous_source or previous_source != PRICE_SOURCE_USED
    )

    def change_for(asset):
        if source_changed:
            return "⚪ مقایسه با ساعت قبل به‌دلیل تغییر منبع انجام نشد"
        return change_text(prices[asset], previous.get(asset))

    if PRICE_SOURCE_USED == "TGJU":
        source_footer = (
            "📊 منبع قیمت: TGJU\n"
            "🔸 طلا: https://t.me/tgjugold\n"
            "🔸 سکه: https://t.me/tgjucoin\n"
            "🔸 ارز: https://t.me/tgjucurrency"
        )
    else:
        reason_line = (
            f"📝 علت استفاده از نوسان: {PRICE_SOURCE_REASON}\n"
            if PRICE_SOURCE_REASON else ""
        )
        source_footer = (
            "📊 منبع قیمت: کانال نوسان\n"
            f"🔗 {NAVASAN_URL}\n"
            + reason_line.rstrip()
        ).strip()

    return f"""🌙✨ زرین ماه
{source_header}

━━━━━━━━━━━━━━━━━━

🟡 طلای ۱۸ عیار
💰 {prices["gold18"]:,} تومان
{change_for("gold18")}

🪙 سکه امامی
💰 {prices["coin"]:,} تومان
{change_for("coin")}

🪙 نیم‌سکه
💰 {prices["half"]:,} تومان
{change_for("half")}

🪙 ربع‌سکه
💰 {prices["quarter"]:,} تومان
{change_for("quarter")}

💵 دلار آزاد
💰 {prices["dollar"]:,} تومان
{change_for("dollar")}

━━━━━━━━━━━━━━━━━━

🕒 آخرین بروزرسانی: {update_time}

{source_footer}

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
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={"chat_id": CHANNEL, "text": message},
        timeout=30,
    )
    print("Telegram HTTP status:", response.status_code)
    print("Telegram response:", response.text)
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")


# =========================================================
# ارسال به ایتایار
# =========================================================
def send_to_eitaa(message):
    if not EITAAYAR_TOKEN:
        raise RuntimeError("EITAAYAR_TOKEN تنظیم نشده است.")
    if not EITAA_CHAT_ID:
        raise RuntimeError("EITAA_CHAT_ID تنظیم نشده است.")

    url = f"https://eitaayar.ir/api/{EITAAYAR_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": EITAA_CHAT_ID.strip().lstrip("@"),
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
        raise RuntimeError("Eitaa API پاسخ JSON معتبر برنگرداند.") from error
    if not result.get("ok"):
        raise RuntimeError(f"Eitaa API error: {result}")
    print("Eitaa message sent successfully.")
    return result


# =========================================================
# اجرای اصلی ربات ساعتی
# =========================================================
def main():
    print("=================================")
    print("Starting ZarinMah TGJU + Navasan + Telegram + Eitaa bot...")
    print("=================================")

    scheduled_run = os.environ.get("SCHEDULED_RUN") == "true"
    watchdog_retry = os.environ.get("WATCHDOG_RETRY") == "true"
    now = datetime.now(TEHRAN)
    print("Tehran time:", now.strftime("%Y-%m-%d %H:%M:%S"))

    current_slot = now.strftime("%Y-%m-%d %H")

    # خاموشی زمان‌بندی‌شده از ۲۲:۰۰ تا ۰۸:۵۹ تهران
    if scheduled_run or watchdog_retry:
        if now.hour >= 22 or now.hour < 9:
            print("Price bot is disabled between 22:00 and 08:59 Tehran time.")
            return

    status = load_send_status()
    telegram_sent = status.get("telegram_hourly", {}).get("slot") == current_slot
    eitaa_sent = status.get("eitaa_hourly", {}).get("slot") == current_slot
    fully_sent = status.get("hourly", {}).get("slot") == current_slot

    if (scheduled_run or watchdog_retry) and fully_sent:
        print(f"Hourly post for {current_slot} has already been sent to all destinations.")
        print("Skipping duplicate message.")
        return

    previous = load_previous_prices()
    prices = get_official_prices()
    message = build_message(prices, previous)

    if not telegram_sent:
        print("Sending price message to Telegram...")
        send_to_telegram(message)
        mark_telegram_sent(current_slot)
        telegram_sent = True
        print("Telegram message sent successfully.")
    else:
        print(f"Telegram message for {current_slot} already sent.")

    if not eitaa_sent:
        send_to_eitaa(message)
        mark_eitaa_sent(current_slot)
        eitaa_sent = True
    else:
        print(f"Eitaa message for {current_slot} already sent.")

    if telegram_sent and eitaa_sent:
        mark_hourly_complete(current_slot)
        print("Telegram + Eitaa hourly send completed.")

    save_current_prices(prices)
    print("Verified prices saved.")
    print("Bot completed successfully.")


if __name__ == "__main__":
    main()
