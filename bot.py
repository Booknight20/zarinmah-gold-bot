import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from telegram import Bot


# =========================
# تنظیمات
# =========================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_USERNAME = "@ZarinMahGold"

TIMEZONE = ZoneInfo("Asia/Tehran")

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
    "half_coin": "https://www.tgju.org/profile/nim",
    "quarter_coin": "https://www.tgju.org/profile/rob",
    "dollar": "https://www.tgju.org/profile/price_Dollar_rl",
}


# =========================
# تبدیل اعداد فارسی/عربی
# =========================

def normalize_digits(text):
    if not text:
        return ""

    translation = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )

    return text.translate(translation)


# =========================
# استخراج اولین عدد معتبر
# =========================

def extract_number(text):
    text = normalize_digits(text)

    # حذف ویرگول و فاصله
    text = text.replace(",", "").replace("٬", "").replace(" ", "")

    match = re.search(r"\d+(?:\.\d+)?", text)

    if not match:
        return None

    return int(float(match.group()))


# =========================
# دریافت نرخ فعلی TGJU
# =========================

def get_current_price(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # روش اصلی: پیدا کردن عبارت «نرخ فعلی»
    text = soup.get_text(" ", strip=True)
    text = normalize_digits(text)

    patterns = [
        r"نرخ فعلی::?\s*([\d,]+)",
        r"نرخ فعلی\s*:\s*([\d,]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            value = extract_number(match.group(1))

            if value:
                return value

    # روش پشتیبان: پیدا کردن عبارت نرخ فعلی و عدد نزدیک آن
    for tag in soup.find_all(string=re.compile("نرخ فعلی")):
        parent_text = tag.parent.get_text(" ", strip=True)

        value = extract_number(parent_text)

        if value:
            return value

    raise ValueError(f"قیمت از TGJU پیدا نشد: {url}")


# =========================
# تبدیل ریال به تومان
# =========================

def rial_to_toman(value):
    return value // 10


# =========================
# فرمت قیمت
# =========================

def format_price(value):
    return f"{value:,}"


# =========================
# دریافت همه قیمت‌ها
# =========================

def get_prices():

    prices = {}

    for name, url in TGJU_URLS.items():

        print(f"در حال دریافت {name} ...")

        rial_price = get_current_price(url)

        toman_price = rial_to_toman(rial_price)

        prices[name] = toman_price

        print(f"{name}: {format_price(toman_price)} تومان")

    return prices


# =========================
# ساخت پیام تلگرام
# =========================

def create_message(prices):

    now = datetime.now(TIMEZONE)

    update_time = now.strftime("%H:%M")

    message = f"""
🌙 *زرین ماه | قیمت طلا، سکه و دلار* 💰

🕒 *آخرین بروزرسانی: {update_time}*

🟡 *طلای ۱۸ عیار*
💰 هر گرم: *{format_price(prices["gold18"])} تومان*

🪙 *سکه امامی*
💰 *{format_price(prices["coin"])} تومان*

🪙 *نیم‌سکه*
💰 *{format_price(prices["half_coin"])} تومان*

🪙 *ربع‌سکه*
💰 *{format_price(prices["quarter_coin"])} تومان*

💵 *دلار آزاد*
💰 *{format_price(prices["dollar"])} تومان*

━━━━━━━━━━━━━━

⚠️ قیمت‌ها بر اساس آخرین نرخ دریافت‌شده از *TGJU* هستند و ممکن است در هر لحظه تغییر کنند.

🌙 *زرین ماه*
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""

    return message.strip()


# =========================
# ارسال به کانال
# =========================

def send_to_telegram(message):

    if not TELEGRAM_BOT_TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    import asyncio

    async def send():
        await bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    asyncio.run(send())


# =========================
# اجرای اصلی
# =========================

def main():

    print("===================================")
    print("🌙 ZarinMah Gold Bot")
    print("===================================")

    prices = get_prices()

    # اطمینان از دریافت همه قیمت‌ها
    required = [
        "gold18",
        "coin",
        "half_coin",
        "quarter_coin",
        "dollar",
    ]

    for item in required:

        if not prices.get(item):
            raise ValueError(
                f"قیمت {item} دریافت نشد."
            )

    message = create_message(prices)

    print("\nپیام آماده ارسال:")
    print(message)

    send_to_telegram()

    print("\n✅ پیام با موفقیت ارسال شد.")


if __name__ == "__main__":
    main()
