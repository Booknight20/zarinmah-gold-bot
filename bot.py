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
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
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
# اختلاف مجاز منابع
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
# نرمال‌سازی برای جستجو
# =========================================================

def normalize_for_search(text):
    text = normalize_digits(clean_text(text))

    text = text.replace("‌", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================================================
# تبدیل عدد به تومان
# =========================================================

def parse_number(value, unit="toman"):
    if not value:
        return None

    text = normalize_digits(clean_text(value))

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
# واکشی پست‌های کانال
# =========================================================

def fetch_channel_posts(channel, max_pages=8):
    all_posts = []
    seen_links = set()
    before_id = None

    for page_number in range(1, max_pages + 1):

        if before_id:
            url = (
                f"https://t.me/s/{channel}"
                f"?before={before_id}"
            )
        else:
            url = (
                f"https://t.me/s/{channel}"
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

        oldest_id = min(post_ids)
        next_before = str(oldest_id)

        if before_id == next_before:
            break

        before_id = next_before

    print(
        f"Total posts collected from "
        f"{channel}: {len(all_posts)}"
    )

    return all_posts


# =========================================================
# استخراج اولین عدد معتبر بعد از برچسب
# =========================================================

def extract_price_after_label(
    text,
    label_pattern,
    minimum,
    maximum,
    unit="toman",
):
    """
    برچسب را پیدا می‌کند و اولین عدد مناسب
    بعد از آن را استخراج می‌کند.
    """

    text = normalize_for_search(text)

    pattern = (
        label_pattern
        + r".{0,120}?"
        + r"([\d,]+)"
        + r"\s*(?:تومان|تومن|ریال)?"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return None

    raw_number = match.group(1)

    # واحد صریح همان حوالی را بررسی می‌کنیم
    nearby = text[
        max(0, match.start()):
        min(
            len(text),
            match.end() + 30,
        )
    ]

    if "ریال" in nearby:
        detected_unit = "rial"
    elif "تومان" in nearby or "تومن" in nearby:
        detected_unit = "toman"
    else:
        detected_unit = unit

    price = parse_number(
        raw_number,
        detected_unit,
    )

    if not price:
        return None

    if minimum <= price <= maximum:
        return price

    return None


# =========================================================
# استخراج یک قیمت از یک خط
# =========================================================

def extract_line_price(
    line,
    label_pattern,
    minimum,
    maximum,
):
    line = normalize_for_search(line)

    match = re.search(
        label_pattern,
        line,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    # تمام عددهای بعد از برچسب
    rest = line[match.end():]

    numbers = re.findall(
        r"([\d,]+)",
        rest,
    )

    for raw_number in numbers:

        # اعداد خیلی کوتاه را نادیده بگیر
        if len(
            raw_number.replace(",", "")
        ) < 4:
            continue

        price = parse_number(
            raw_number,
            "toman",
        )

        if (
            price
            and minimum <= price <= maximum
        ):
            return price

    return None


# =========================================================
# استخراج طلای ۱۸
# =========================================================

def extract_gold18_mesghal(text):
    patterns = [
        r"طلای\s*(?:18|۱۸)\s*عیار",
        r"طلای\s*(?:18|۱۸)",
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

    # تلاش خط‌به‌خط
    for line in clean_text(text).splitlines():

        for pattern in patterns:

            price = extract_line_price(
                line,
                pattern,
                1_000_000,
                500_000_000,
            )

            if price:
                return price

    return None


# =========================================================
# استخراج دلار مثقال
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

    # تلاش خط به خط
    for line in clean_text(text).splitlines():

        for pattern in patterns:

            price = extract_line_price(
                line,
                pattern,
                100_000,
                1_000_000,
            )

            if price:
                return price

    return None


# =========================================================
# استخراج سکه امامی
# =========================================================

def extract_coin_mesghal(text):
    patterns = [
        r"سکه\s*امامی",
    ]

    for pattern in patterns:

        price = extract_price_after_label(
            text,
            pattern,
            10_000_000,
            1_000_000_000,
            "toman",
        )

        if price:
            return price

    for line in clean_text(text).splitlines():

        for pattern in patterns:

            price = extract_line_price(
                line,
                pattern,
                10_000_000,
                1_000_000_000,
            )

            if price:
                return price

    return None


# =========================================================
# استخراج نیم سکه
# =========================================================

def extract_half_mesghal(text):
    patterns = [
        r"نیم\s*سکه",
    ]

    for pattern in patterns:

        price = extract_price_after_label(
            text,
            pattern,
            5_000_000,
            500_000_000,
            "toman",
        )

        if price:
            return price

    for line in clean_text(text).splitlines():

        for pattern in patterns:

            price = extract_line_price(
                line,
                pattern,
                5_000_000,
                500_000_000,
            )

            if price:
                return price

    return None


# =========================================================
# استخراج ربع سکه
# =========================================================

def extract_quarter_mesghal(text):
    patterns = [
        r"ربع\s*سکه",
    ]

    for pattern in patterns:

        price = extract_price_after_label(
            text,
            pattern,
            2_000_000,
            300_000_000,
            "toman",
        )

        if price:
            return price

    for line in clean_text(text).splitlines():

        for pattern in patterns:

            price = extract_line_price(
                line,
                pattern,
                2_000_000,
                300_000_000,
            )

            if price:
                return price

    return None


# =========================================================
# استخراج طلای ۱۸ عمومی
# =========================================================

def extract_gold18(
    text,
    unit,
):
    text = normalize_for_search(text)

    patterns = [
        (
            r"طلای\s*(?:18|۱۸)\s*عیار"
            r".{0,150}?"
            r"([\d,]+)"
            r"\s*(تومان|تومن|ریال)?"
        ),
        (
            r"طلای\s*(?:18|۱۸)"
            r".{0,150}?"
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

        raw_number = match.group(1)
        explicit_unit = match.group(2)

        detected_unit = unit

        if explicit_unit == "ریال":
            detected_unit = "rial"
        elif (
            explicit_unit == "تومان"
            or explicit_unit == "تومن"
        ):
            detected_unit = "toman"

        price = parse_number(
            raw_number,
            detected_unit,
        )

        if (
            price
            and 100_000 <= price <= 500_000_000
        ):
            return price

    return None


# =========================================================
# استخراج دلار عمومی
# =========================================================

def extract_dollar(
    text,
    unit,
):
    text = normalize_for_search(text)

    candidates = []

    # -----------------------------------------------------
    # TGJU - فقط قیمت دلار اصلی
    # -----------------------------------------------------

    tgju_match = re.search(
        r"#قیمت[_\s]*دلار
