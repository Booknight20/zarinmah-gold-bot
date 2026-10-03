import os
import re
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
# تبدیل اعداد فارسی و عربی به انگلیسی
# ==========================================

def normalize_digits(text):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )
    return text.translate(table)


# ==========================================
# دریافت نرخ فعلی از TGJU
# ==========================================

def get_tgju_price(url):
    print(f"در حال دریافت: {url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    page_text = soup.get_text(" ", strip=True)
    page_text = normalize_digits(page_text)

    # نرخ فعلی در صفحات TGJU
    patterns = [
        r"نرخ فعلی\s*:\s*:?\s*([\d,]+)",
        r"نرخ فعلی::\s*([\d,]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, page_text)

        if match:
            value = match.group(1)
            value = value.replace(",", "")

            price = int(value)

            print(f"قیمت ریالی: {price:,}")

            return price

    raise RuntimeError(
        f"قیمت فعلی از TGJU پیدا نشد: {url}"
    )


# ==========================================
# تبدیل ریال به تومان
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

        toman_price = rial_to_toman(rial_price)

        prices[name] = toman_price

        print(
            f"{name}: {toman_price:,} تومان"
        )

    return prices


# ==========================================
# ساخت متن پیام
# ==========================================

def build_message(prices):

    now = datetime.now(TEHRAN)

    update_time = now.strftime("%H:%M")

    return f"""🌙 زرین ماه | قیمت طلا، سکه و دلار 💰

🕒 آخرین بروزرسانی: {update_time}

🟡 طلای ۱۸ عیار
💰 هر گرم: {prices["gold18"]:,} تومان

🪙 سکه امامی
💰 {prices["coin"]:,} تومان

🪙 نیم‌سکه
💰 {prices["half"]:,} تومان

🪙 ربع‌سکه
💰 {prices["quarter"]:,} تومان

💵 دلار آزاد
💰 {prices["dollar"]:,} تومان

━━━━━━━━━━━━━━

⚠️ قیمت‌ها بر اساس آخرین نرخ دریافت‌شده از TGJU هستند و ممکن است در هر لحظه تغییر کنند.

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
            "TELEGRAM_BOT_TOKEN در GitHub تنظیم نشده است."
        )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHANNEL,
        "text": message,
    }

    response = requests.post(
        url,
        data=data,
        timeout=30
    )

    print("Telegram status:", response.status_code)
    print("Telegram response:", response.text)

    if not response.ok:
        raise RuntimeError(
            f"Telegram API error: {response.text}"
        )

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result}"
        )

    print("✅ پیام با موفقیت ارسال شد.")


# ==========================================
# اجرای اصلی
# ==========================================

def main():

    print("================================")
    print("🌙 ZarinMah Gold Bot")
    print("================================")

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

    message = build_message(prices)

    print("\n----- پیام نهایی -----")
    print(message)
    print("----------------------\n")

    send_to_telegram(message)


if __name__ == "__main__":
    main()
