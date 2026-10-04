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

# hourly یا daily
BOT_MODE = os.environ.get("BOT_MODE", "hourly")

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
# تبدیل میلادی به شمسی
# ==========================================

def gregorian_to_jalali(gy, gm, gd):

    g_days_in_month = [
        31, 28, 31, 30, 31, 30,
        31, 31, 30, 31, 30, 31
    ]

    gy2 = gy - 1600
    jy = 979

    if gm > 2:
        gy2 += 1

    days = (
        365 * gy2
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
    )

    for i in range(gm - 1):
        days += g_days_in_month[i]

    if gm > 2 and (
        gy % 4 == 0 and
        (gy % 100 != 0 or gy % 400 == 0)
    ):
        days += 1

    days += gd - 1
    days -= 79

    j_np = days // 12053
    days %= 12053

    jy += 33 * j_np
    jy += 4 * (days // 1461)

    days %= 1461

    if days >= 366:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30

    return jy, jm, jd


# ==========================================
# روزهای هفته
# ==========================================

WEEKDAYS = {
    0: "دوشنبه",
    1: "سه‌شنبه",
    2: "چهارشنبه",
    3: "پنجشنبه",
    4: "جمعه",
    5: "شنبه",
    6: "یکشنبه",
}


JALALI_MONTHS = {
    1: "فروردین",
    2: "اردیبهشت",
    3: "خرداد",
    4: "تیر",
    5: "مرداد",
    6: "شهریور",
    7: "مهر",
    8: "آبان",
    9: "آذر",
    10: "دی",
    11: "بهمن",
    12: "اسفند",
}


# ==========================================
# مناسبت‌های ثابت
# ==========================================

OCCASIONS = {
    (1, 1): "نوروز",
    (1, 2): "نوروز",
    (1, 3): "نوروز",
    (1, 4): "نوروز",
    (1, 12): "روز جمهوری اسلامی ایران",
    (1, 13): "روز طبیعت",
    (2, 1): "روز کارگر",
    (3, 14): "رحلت امام خمینی",
    (3, 15): "قیام ۱۵ خرداد",
    (6, 31): "روز صنعت دفاعی",
    (7, 1): "بازگشایی مدارس",
    (7, 7): "روز آتش‌نشانی و ایمنی",
    (7, 20): "روز حافظ",
    (8, 13): "روز دانش‌آموز",
    (9, 16): "روز دانشجو",
    (10, 1): "روز ثبت احوال",
    (11, 22): "پیروزی انقلاب اسلامی",
    (12, 29): "روز ملی شدن صنعت نفت",
}


def get_occasion(jm, jd):

    occasion = OCCASIONS.get((jm, jd))

    if occasion:
        return f"🎉 {occasion}"

    return "🌱 امروز را با انرژی و تصمیم‌های آگاهانه شروع کنیم."


# ==========================================
# دریافت قیمت TGJU
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

            value = match.group(1).replace(",", "")

            price = int(value)

            print(f"قیمت ریالی: {price:,}")

            return price

    raise RuntimeError(
        f"قیمت فعلی از TGJU پیدا نشد: {url}"
    )


def rial_to_toman(value):
    return value // 10


# ==========================================
# دریافت همه قیمت‌ها
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
            f"{name}: {toman_price:,} تومان"
        )

    return prices


# ==========================================
# قیمت قبلی
# ==========================================

def load_previous_prices():

    if not os.path.exists(PREVIOUS_FILE):
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
            f"⚠️ خطا در خواندن قیمت قبلی: {error}"
        )

        return None


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

    print("✅ قیمت‌های فعلی ذخیره شدند.")


# ==========================================
# تغییر قیمت
# ==========================================

def get_change_percent(current, previous):

    if not previous:
        return 0

    return (
        (current - previous)
        / previous
    ) * 100


def get_change_text(current, previous):

    if previous is None:
        return "🆕 اولین ثبت"

    difference = current - previous

    percent = get_change_percent(
        current,
        previous
    )

    if difference > 0:

        return (
            f"🟢 ▲ +{difference:,} تومان "
            f"({percent:+.2f}٪)"
        )

    if difference < 0:

        return (
            f"🔴 ▼ {difference:,} تومان "
            f"({percent:+.2f}٪)"
        )

    return "⚪ ➖ بدون تغییر"


# ==========================================
# پیام ساعتی فعلی
# ==========================================

def build_hourly_message(
    prices,
    previous_prices
):

    now = datetime.now(TEHRAN)

    changes = {}

    for item in [
        "gold18",
        "coin",
        "half",
        "quarter",
        "dollar"
    ]:

        changes[item] = get_change_text(
            prices[item],
            previous_prices.get(item)
            if previous_prices
            else None
        )

    return f"""🌙✨ زرین ماه
💎 قیمت لحظه‌ای طلا، سکه و دلار

━━━━━━━━━━━━━━━━━━

🟡 طلای ۱۸ عیار
💰 {prices["gold18"]:,} تومان
{changes["gold18"]}

🪙 سکه امامی
💰 {prices["coin"]:,} تومان
{changes["coin"]}

🪙 نیم‌سکه
💰 {prices["half"]:,} تومان
{changes["half"]}

🪙 ربع‌سکه
💰 {prices["quarter"]:,} تومان
{changes["quarter"]}

💵 دلار آزاد
💰 {prices["dollar"]:,} تومان
{changes["dollar"]}

━━━━━━━━━━━━━━━━━━

🕒 آخرین بروزرسانی: {now.strftime("%H:%M")}

📊 منبع نرخ‌ها: TGJU
⚠️ قیمت‌ها ممکن است در هر لحظه تغییر کنند.

━━━━━━━━━━━━━━━━━━

🌙 زرین ماه
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""


# ==========================================
# تحلیل بازار
# ==========================================

def analyze_market(prices, previous):

    if not previous:

        return {
            "trend": "⚪ خنثی",
            "summary": "هنوز داده کافی برای مقایسه روند وجود ندارد.",
            "bullish": "در صورت رشد دلار و افزایش تقاضا، احتمال رشد طلا بیشتر می‌شود.",
            "neutral": "در صورت ثبات دلار، نوسان محدود محتمل است.",
            "bearish": "در صورت افت دلار، احتمال اصلاح قیمت طلا وجود دارد.",
        }

    gold = get_change_percent(
        prices["gold18"],
        previous.get("gold18")
    )

    coin = get_change_percent(
        prices["coin"],
        previous.get("coin")
    )

    dollar = get_change_percent(
        prices["dollar"],
        previous.get("dollar")
    )

    positive = sum(
        value > 0.10
        for value in [gold, coin, dollar]
    )

    negative = sum(
        value < -0.10
        for value in [gold, coin, dollar]
    )

    if positive >= 2:

        return {
            "trend": "🟢 متمایل به صعودی",
            "summary": (
                "دلار، طلا و سکه در کوتاه‌مدت "
                "تمایل افزایشی نشان می‌دهند."
            ),
            "bullish": (
                "اگر دلار و تقاضای بازار تقویت شوند، "
                "احتمال ادامه حرکت صعودی وجود دارد."
            ),
            "neutral": (
                "در صورت آرام شدن دلار، "
                "احتمال نوسان و استراحت قیمت‌ها وجود دارد."
            ),
            "bearish": (
                "افت دلار می‌تواند باعث اصلاح بخشی "
                "از رشد اخیر طلا و سکه شود."
            ),
        }

    if negative >= 2:

        return {
            "trend": "🔴 متمایل به نزولی",
            "summary": (
                "هم‌جهتی کاهشی دلار، طلا و سکه "
                "فشار فروش کوتاه‌مدت را نشان می‌دهد."
            ),
            "bullish": (
                "بازگشت دلار یا افزایش تقاضا "
                "می‌تواند روند را برگرداند."
            ),
            "neutral": (
                "با توقف افت دلار، احتمال تثبیت "
                "قیمت‌ها در محدوده فعلی وجود دارد."
            ),
            "bearish": (
                "ادامه افت دلار می‌تواند "
                "فشار نزولی بیشتری ایجاد کند."
            ),
        }

    return {
        "trend": "🟡 خنثی و نوسانی",
        "summary": (
            "حرکت قیمت‌ها یک‌جهت نیست و بازار "
            "در وضعیت نوسانی قرار دارد."
        ),
        "bullish": (
            "عبور دلار و طلا از مقاومت‌های کوتاه‌مدت "
            "می‌تواند احتمال رشد را بیشتر کند."
        ),
        "neutral": (
            "ادامه نوسان در محدوده فعلی "
            "سناریوی محتمل‌تری است."
        ),
        "bearish": (
            "شکست حمایت‌های کوتاه‌مدت "
            "می‌تواند اصلاح قیمت را فعال کند."
        ),
    }


# ==========================================
# حمایت و مقاومت تقریبی
# ==========================================

def get_levels(price):

    step = max(
        100000,
        round(price * 0.01)
    )

    support = price - step
    resistance = price + step

    return support, resistance


# ==========================================
# پیام روزانه
# ==========================================

def build_daily_message(
    prices,
    previous_prices
):

    now = datetime.now(TEHRAN)

    jy, jm, jd = gregorian_to_jalali(
        now.year,
        now.month,
        now.day
    )

    weekday = WEEKDAYS[now.weekday()]

    occasion = get_occasion(jm, jd)

    analysis = analyze_market(
        prices,
        previous_prices
    )

    support, resistance = get_levels(
        prices["gold18"]
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

    dollar_change = get_change_text(
        prices["dollar"],
        previous_prices.get("dollar")
        if previous_prices
        else None
    )

    return f"""🌙✨ **زرین ماه | تقویم و نبض بازار**

📅 **{weekday} {jd} {JALALI_MONTHS[jm]} {jy}**
🗓 {now.strftime("%Y/%m/%d")}

━━━━━━━━━━━━━━━━━━

🎉 **مناسبت امروز**
{occasion}

💡 **یادآوری امروز**
تصمیم‌گیری در بازار طلا و ارز را
بر اساس هیجان لحظه‌ای انجام ندهید.

━━━━━━━━━━━━━━━━━━

💎 **نبض بازار ایران**

🟡 **طلای ۱۸ عیار**
💰 {prices["gold18"]:,} تومان
{gold_change}

🪙 **سکه امامی**
💰 {prices["coin"]:,} تومان
{coin_change}

💵 **دلار آزاد**
💰 {prices["dollar"]:,} تومان
{dollar_change}

━━━━━━━━━━━━━━━━━━

📊 **تحلیل کوتاه‌مدت**

وضعیت فعلی:
**{analysis["trend"]}**

{analysis["summary"]}

🔺 **سناریوی صعودی**
{analysis["bullish"]}

➖ **سناریوی خنثی**
{analysis["neutral"]}

🔻 **سناریوی نزولی**
{analysis["bearish"]}

━━━━━━━━━━━━━━━━━━

🎯 **محدوده تقریبی طلای ۱۸ عیار**

حمایت:
**{support:,} تومان**

مقاومت:
**{resistance:,} تومان**

━━━━━━━━━━━━━━━━━━

⚠️ این تحلیل احتمالی است و توصیه قطعی
برای خرید یا فروش نیست.

🕚 زمان بروزرسانی:
**{now.strftime("%H:%M")}**

📊 منبع قیمت‌ها: TGJU

━━━━━━━━━━━━━━━━━━

🌙 **زرین ماه**
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""


# ==========================================
# ارسال تلگرام
# ==========================================

def send_to_telegram(message):

    if not BOT_TOKEN:

        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    url = (
        "https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    data = {
        "chat_id": CHANNEL,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    response = requests.post(
        url,
        data=data,
        timeout=30
    )

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
    print(f"MODE: {BOT_MODE}")
    print("================================")

    previous_prices = load_previous_prices()

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

    if BOT_MODE == "daily":

        message = build_daily_message(
            prices,
            previous_prices
        )

    else:

        message = build_hourly_message(
            prices,
            previous_prices
        )

    print("\n----- پیام نهایی -----")
    print(message)
    print("----------------------\n")

    send_to_telegram(message)

    save_current_prices(prices)


if __name__ == "__main__":
    main()
