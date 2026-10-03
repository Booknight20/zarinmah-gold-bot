import os
import re
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# ==========================================
# تنظیمات
# ==========================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL = "@ZarinMahGold"

TEHRAN = ZoneInfo("Asia/Tehran")

PREVIOUS_FILE = "previous_prices.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    )
}

TGJU_URLS = {
    "gold18": "https://www.tgju.org/profile/geram18",
    "coin": "https://www.tgju.org/profile/sekee",
    "half": "https://www.tgju.org/profile/nim",
    "quarter": "https://www.tgju.org/profile/rob",
    "dollar": "https://www.tgju.org/profile/price_dollar_rl",
}


# ==========================================
# تبدیل اعداد فارسی و عربی
# ==========================================

def normalize_digits(text):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )

    return text.translate(table)


# ==========================================
# دریافت قیمت از TGJU
# ==========================================

def get_tgju_price(url):

    print(f"در حال دریافت: {url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    page_text = soup.get_text(
        " ",
        strip=True
    )

    page_text = normalize_digits(page_text)

    patterns = [
        r"نرخ فعلی\s*:\s*:?\s*([\d,]+)",
        r"نرخ فعلی::\s*([\d,]+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            page_text
        )

        if match:

            value = match.group(1)

            value = value.replace(
                ",",
                ""
            )

            price = int(value)

            print(
                f"قیمت ریالی: {price:,}"
            )

            return price

    raise RuntimeError(
        f"قیمت فعلی از TGJU پیدا نشد: {url}"
    )


# ==========================================
# ریال به تومان
# ==========================================

def rial_to_toman(value):
    return value // 10


# ==========================================
# گرفتن همه قیمت‌ها
# ==========================================

def get_all_prices():

    prices = {}

    for name, url in TGJU_URLS.items():

        rial_price = get_tgju_price(url)

        toman_price = rial_to_toman(
            rial_price
        )

        prices[name] = toman_price

        print(
            f"{name}: "
            f"{toman_price:,} تومان"
        )

    return prices


# ==========================================
# خواندن قیمت‌های ساعت قبل
# ==========================================

def load_previous_prices():

    if not os.path.exists(PREVIOUS_FILE):

        print(
            "⚪ فایل قیمت قبلی وجود ندارد."
        )

        return None

    try:

        with open(
            PREVIOUS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as error:

        print(
            f"⚠️ خطا در خواندن قیمت قبلی: "
            f"{error}"
        )

        return None


# ==========================================
# ذخیره قیمت‌های فعلی
# ==========================================

def save_current_prices(prices):

    with open(
        PREVIOUS_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            prices,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        "✅ قیمت‌های فعلی ذخیره شدند."
    )


# ==========================================
# نمایش تغییر قیمت
# ==========================================

def get_change_text(
    current,
    previous
):

    if previous is None:

        return "🆕 اولین ثبت"

    difference = current - previous

    if difference > 0:

        return (
            f"🟢 ▲ "
            f"+{difference:,} تومان"
        )

    if difference < 0:

        return (
            f"🔴 ▼ "
            f"{difference:,} تومان"
        )

    return "⚪ ➖ بدون تغییر"


# ==========================================
# ساخت پیام
# ==========================================

def build_message(
    prices,
    previous_prices
):

    now = datetime.now(TEHRAN)

    update_time = now.strftime(
        "%H:%M"
    )

    gold_change = get_change_text(
        prices["gold18"],
        previous_prices.get("gold18")
        if previous_prices
        else None
    )

    coin_change = get_change_text(
        prices["coin"],
        previous_prices.get("coin")
        if previous_prices
        else None
    )

    half_change = get_change_text(
        prices["half"],
        previous_prices.get("half")
        if previous_prices
        else None
    )

    quarter_change = get_change_text(
        prices["quarter"],
        previous_prices.get("quarter")
        if previous_prices
        else None
    )

    dollar_change = get_change_text(
        prices["dollar"],
        previous_prices.get("dollar")
        if previous_prices
        else None
    )

    return f"""🌙✨ زرین ماه
💎 قیمت لحظه‌ای طلا، سکه و دلار

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

📊 منبع نرخ‌ها: TGJU
⚠️ قیمت‌ها ممکن است در هر لحظه تغییر کنند.

━━━━━━━━━━━━━━━━━━

🌙 زرین ماه
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""


# ==========================================
# ارسال به تلگرام
# ==========================================

def send_to_telegram(message):

    if not BOT_TOKEN:

        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN "
            "تنظیم نشده است."
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
        timeout=30
    )

    print(
        "Telegram status:",
        response.status_code
    )

    print(
        "Telegram response:",
        response.text
    )

    if not response.ok:

        raise RuntimeError(
            f"Telegram API error: "
            f"{response.text}"
        )

    result = response.json()

    if not result.get("ok"):

        raise RuntimeError(
            f"Telegram API error: "
            f"{result}"
        )

    print(
        "✅ پیام با موفقیت ارسال شد."
    )


# ==========================================
# اجرای اصلی
# ==========================================

def main():

    print(
        "================================"
    )

    print(
        "🌙 ZarinMah Gold Bot"
    )

    print(
        "================================"
    )

    # قیمت‌های قبلی
    previous_prices = (
        load_previous_prices()
    )

    # قیمت‌های فعلی
    prices = get_all_prices()

    required = [
        "gold18",
        "coin",
        "half",
        "quarter",
        "dollar",
    ]

    for item in required:

        if not prices.get(item):

            raise RuntimeError(
                f"قیمت {item} دریافت نشد."
            )

    # ساخت پیام
    message = build_message(
        prices,
        previous_prices
    )

    print(
        "\n----- پیام نهایی -----"
    )

    print(message)

    print(
        "----------------------\n"
    )

    # اول پیام را ارسال می‌کنیم
    send_to_telegram(
        message
    )

    # فقط بعد از ارسال موفق،
    # قیمت‌های جدید را ذخیره می‌کنیم
    save_current_prices(
        prices
    )


if __name__ == "__main__":

    main()
