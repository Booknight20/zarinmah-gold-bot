import os
import re
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# =========================
# تنظیمات اصلی
# =========================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL = "@ZarinMahGold"

TEHRAN = ZoneInfo("Asia/Tehran")

PREVIOUS_FILE = "previous_prices.json"

SOURCE_URL = "https://gheymat.online/prices"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/webp,*/*;q=0.8"
    ),
}

# کدهای دارایی در سایت قیمت آنلاین
PRICE_CODES = {
    "gold18": "GOLD18",
    "coin": "SEKE",
    "half": "SEKEN",
    "quarter": "SEKER",
    "dollar": "USD",
}


# =========================
# تبدیل اعداد فارسی و عربی
# =========================

def normalize_digits(value):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )

    return str(value).translate(table)


# =========================
# تبدیل متن قیمت به عدد تومان
# =========================

def parse_price_text(value):
    """
    نمونه‌های قابل پشتیبانی:

    26,432,000
    ۲۶٬۴۳۲٬۰۰۰
    24.036 م.ن
    235912

    خروجی:
    عدد صحیح به تومان
    """

    text = normalize_digits(value)

    text = (
        text.replace("٬", ",")
        .replace("،", ",")
        .replace("\u200c", " ")
    )

    text = re.sub(r"\s+", " ", text).strip()

    # درصد قیمت نیست
    if "%" in text:
        return None

    # عدد را پیدا می‌کنیم
    match = re.search(
        r"\d+(?:[.,]\d+)*",
        text
    )

    if not match:
        return None

    number_text = match.group(0)

    # مثال:
    # 26,432,000
    if "," in number_text:
        try:
            number = float(number_text.replace(",", ""))
        except ValueError:
            return None

    else:
        try:
            number = float(number_text)
        except ValueError:
            return None

    suffix = text[match.end():].strip()

    # میلیون تومان
    if "م.ن" in suffix:
        number *= 1_000_000

    # میلیون ریال/حالت‌های مشابه
    elif "م.د" in suffix:
        number *= 1_000_000

    # هزار
    elif "هزار" in suffix:
        number *= 1_000

    return int(round(number))


# =========================
# پیدا کردن ردیف یک دارایی
# =========================

def find_price_row(soup, code):
    code = code.upper()

    for row in soup.find_all("tr"):

        row_text = " ".join(
            row.stripped_strings
        ).upper()

        if code not in row_text:
            continue

        cells = row.find_all(
            ["td", "th"]
        )

        if len(cells) >= 3:
            return cells

    return None


# =========================
# دریافت قیمت از قیمت آنلاین
# =========================

def get_price_online_price(code):

    last_error = None

    for attempt in range(1, 6):

        try:

            print(
                f"Fetching {code} "
                f"(attempt {attempt}/5)..."
            )

            response = requests.get(
                SOURCE_URL,
                headers=HEADERS,
                timeout=30,
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            cells = find_price_row(
                soup,
                code
            )

            if not cells:
                raise RuntimeError(
                    f"ردیف {code} "
                    f"در صفحه قیمت آنلاین پیدا نشد."
                )

            # جدول:
            #
            # دارایی | خرید | فروش | تغییر
            #
            # برای ربات از ستون «خرید» استفاده می‌کنیم.

            price_text = cells[1].get_text(
                " ",
                strip=True
            )

            price = parse_price_text(
                price_text
            )

            if price is None or price <= 0:
                raise RuntimeError(
                    f"قیمت {code} "
                    f"قابل استخراج نیست: "
                    f"{price_text}"
                )

            print(
                f"{code} = "
                f"{price:,} تومان"
            )

            return price

        except Exception as error:

            last_error = error

            print(
                f"Attempt {attempt} failed "
                f"for {code}: {error}"
            )

    raise RuntimeError(
        f"دریافت قیمت {code} از قیمت آنلاین "
        f"پس از 5 تلاش ناموفق بود. "
        f"آخرین خطا: {last_error}"
    )


# =========================
# دریافت همه قیمت‌ها
# =========================

def get_all_prices():

    prices = {}

    for name, code in PRICE_CODES.items():

        prices[name] = get_price_online_price(
            code
        )

    return prices


# =========================
# خواندن قیمت‌های قبلی
# =========================

def load_previous_prices():

    if not os.path.exists(
        PREVIOUS_FILE
    ):
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
            "Could not load previous prices:",
            error
        )

        return None


# =========================
# ذخیره قیمت‌های جدید
# =========================

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


# =========================
# محاسبه تغییر قیمت
# =========================

def get_change_text(
    current,
    previous
):

    if previous is None:
        return "🆕 اولین ثبت"

    difference = current - previous

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


# =========================
# ساخت پیام تلگرام
# =========================

def build_message(
    prices,
    previous_prices
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
        previous_prices.get("gold18")
    )

    coin_change = get_change_text(
        prices["coin"],
        previous_prices.get("coin")
    )

    half_change = get_change_text(
        prices["half"],
        previous_prices.get("half")
    )

    quarter_change = get_change_text(
        prices["quarter"],
        previous_prices.get("quarter")
    )

    dollar_change = get_change_text(
        prices["dollar"],
        previous_prices.get("dollar")
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

📊 منبع نرخ‌ها: قیمت آنلاین
⚠️ قیمت‌ها ممکن است در هر لحظه تغییر کنند.

━━━━━━━━━━━━━━━━━━

🌙 زرین ماه
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""


# =========================
# ارسال پیام به تلگرام
# =========================

def send_to_telegram(message):

    if not BOT_TOKEN:

        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    url = (
        f"https://api.telegram.org/"
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
        response.status_code
    )

    print(
        "Telegram response:",
        response.text
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):

        raise RuntimeError(
            f"Telegram API error: {result}"
        )


# =========================
# اجرای اصلی
# =========================

def main():

    print(
        "================================"
    )

    print(
        "Starting ZarinMah price bot..."
    )

    print(
        "================================"
    )

    # قیمت قبلی
    previous_prices = (
        load_previous_prices()
    )

    # قیمت جدید
    print(
        "Fetching latest prices..."
    )

    prices = get_all_prices()

    print(
        "Prices received:",
        prices
    )

    # بررسی همه قیمت‌ها
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
                f"قیمت {item} معتبر دریافت نشد."
            )

    # ساخت پیام
    message = build_message(
        prices,
        previous_prices
    )

    print(
        "Sending message to Telegram..."
    )

    # ارسال پیام
    send_to_telegram(
        message
    )

    print(
        "Telegram message sent successfully."
    )

    # فقط بعد از ارسال موفق ذخیره کن
    save_current_prices(
        prices
    )

    print(
        "Previous prices saved successfully."
    )

    print(
        "Bot completed successfully."
    )


# =========================
# شروع برنامه
# =========================

if __name__ == "__main__":
    main()
