import os
import re
import json
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# =========================
# CONFIG
# =========================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
BOT_MODE = os.environ.get("BOT_MODE", "hourly")

CHANNEL = "@ZarinMahGold"
TEHRAN = ZoneInfo("Asia/Tehran")

PREVIOUS_FILE = "previous_prices.json"
HISTORY_FILE = "market_history.json"

MAX_HISTORY_DAYS = 30

TGJU_URLS = {
    "gold18": "https://www.tgju.org/profile/geram18",
    "coin": "https://www.tgju.org/profile/sekee",
    "half": "https://www.tgju.org/profile/nim",
    "quarter": "https://www.tgju.org/profile/rob",
    "dollar": "https://www.tgju.org/profile/price_dollar_rl",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    )
}


# =========================
# DATE / CALENDAR
# =========================

WEEKDAYS_FA = [
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنجشنبه",
    "جمعه",
    "شنبه",
    "یکشنبه",
]

PERSIAN_MONTHS = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]


def gregorian_to_jalali(gy, gm, gd):
    """
    تبدیل تاریخ میلادی به شمسی.
    """
    g_days_in_month = [
        31, 28, 31, 30, 31, 30,
        31, 31, 30, 31, 30, 31
    ]

    j_days_in_month = [
        31, 31, 31, 31, 31, 31,
        30, 30, 30, 30, 30, 29
    ]

    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1

    g_day_no = (
        365 * gy2
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
    )

    for i in range(gm2):
        g_day_no += g_days_in_month[i]

    if gm2 > 1 and (
        gy % 4 == 0 and
        (gy % 100 != 0 or gy % 400 == 0)
    ):
        g_day_no += 1

    g_day_no += gd2

    j_day_no = g_day_no - 79

    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    i = 0

    while (
        i < 11
        and j_day_no >= j_days_in_month[i]
    ):
        j_day_no -= j_days_in_month[i]
        i += 1

    jm = i + 1
    jd = j_day_no + 1

    return jy, jm, jd


def get_jalali_date(dt):
    return gregorian_to_jalali(
        dt.year,
        dt.month,
        dt.day
    )


def get_date_info():
    now = datetime.now(TEHRAN)

    jy, jm, jd = get_jalali_date(now)

    weekday = WEEKDAYS_FA[now.weekday()]
    jalali_date = (
        f"{jd} {PERSIAN_MONTHS[jm - 1]} {jy}"
    )

    gregorian_date = now.strftime("%Y/%m/%d")

    return {
        "now": now,
        "weekday": weekday,
        "jalali": jalali_date,
        "gregorian": gregorian_date,
    }


# =========================
# OCCASIONS
# =========================

OCCASIONS = {
    # نمونه مناسبت‌های ثابت
    # این بخش قابل توسعه است.
}


def get_today_occasions():
    info = get_date_info()
    jy, jm, jd = get_jalali_date(info["now"])

    key = f"{jm:02d}-{jd:02d}"

    occasions = OCCASIONS.get(key, [])

    if not occasions:
        return "امروز مناسبت ثبت‌شده‌ای در فهرست این ربات ندارد."

    return "\n".join(
        f"• {item}"
        for item in occasions
    )


# =========================
# NUMBER HELPERS
# =========================

def normalize_digits(text):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )
    return text.translate(table)


def rial_to_toman(value):
    return value // 10


# =========================
# TGJU
# =========================

def get_tgju_price(url):
    max_attempts = 5

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=30,
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            page_text = normalize_digits(
                soup.get_text(
                    " ",
                    strip=True
                )
            )

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
                    value = value.replace(",", "")
                    return int(value)

            raise RuntimeError(
                f"قیمت فعلی از TGJU پیدا نشد: {url}"
            )

        except Exception as error:
            print(
                f"TGJU attempt {attempt}/{max_attempts}: "
                f"{error}"
            )

            if attempt < max_attempts:
                wait_seconds = attempt * 5

                print(
                    f"Retrying in "
                    f"{wait_seconds} seconds..."
                )

                time.sleep(wait_seconds)

    raise RuntimeError(
        f"دریافت قیمت از TGJU پس از "
        f"{max_attempts} تلاش ناموفق بود."
    )


def get_all_prices():
    prices = {}

    for name, url in TGJU_URLS.items():
        rial_price = get_tgju_price(url)
        prices[name] = rial_to_toman(
            rial_price
        )

    return prices


# =========================
# PREVIOUS PRICES
# =========================

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
            f"Could not load previous prices: {error}"
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


# =========================
# MARKET HISTORY
# =========================

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except Exception as error:
        print(
            f"Could not load history: {error}"
        )
        return []


def save_history(history):
    with open(
        HISTORY_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            history,
            file,
            ensure_ascii=False,
            indent=2
        )


def add_history_record(history, prices):
    now = datetime.now(TEHRAN)

    record = {
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "gold18": prices["gold18"],
        "coin": prices["coin"],
        "half": prices["half"],
        "quarter": prices["quarter"],
        "dollar": prices["dollar"],
    }

    history.append(record)

    cutoff = now - timedelta(
        days=MAX_HISTORY_DAYS
    )

    filtered = []

    for item in history:
        try:
            item_time = datetime.fromisoformat(
                item["timestamp"]
            )

            if item_time >= cutoff:
                filtered.append(item)

        except Exception:
            continue

    return filtered


# =========================
# MARKET ANALYSIS
# =========================

def historical_change(
    history,
    current_price,
    key,
    hours
):
    if not history or current_price <= 0:
        return None

    now = datetime.now(TEHRAN)

    target = now - timedelta(
        hours=hours
    )

    candidates = []

    for item in history:
        try:
            item_time = datetime.fromisoformat(
                item["timestamp"]
            )

            if item_time <= target:
                candidates.append(item)

        except Exception:
            continue

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x["timestamp"]
    )

    old_price = candidates[-1].get(key)

    if not old_price:
        return None

    return (
        (current_price - old_price)
        / old_price
    ) * 100


def get_window_records(
    history,
    hours
):
    now = datetime.now(TEHRAN)

    cutoff = now - timedelta(
        hours=hours
    )

    result = []

    for item in history:
        try:
            item_time = datetime.fromisoformat(
                item["timestamp"]
            )

            if item_time >= cutoff:
                result.append(item)

        except Exception:
            continue

    return result


def get_real_levels(
    history,
    key,
    current_price
):
    records = get_window_records(
        history,
        72
    )

    values = []

    for item in records:
        value = item.get(key)

        if isinstance(value, (int, float)):
            values.append(value)

    if not values:
        return None, None

    supports = [
        value
        for value in values
        if value < current_price
    ]

    resistances = [
        value
        for value in values
        if value > current_price
    ]

    support = max(supports) if supports else None
    resistance = (
        min(resistances)
        if resistances
        else None
    )

    if support is None:
        support = int(
            current_price * 0.99
        )

    if resistance is None:
        resistance = int(
            current_price * 1.01
        )

    return support, resistance


def determine_trend(changes):
    values = [
        value
        for value in changes
        if value is not None
    ]

    if not values:
        return "نامشخص"

    average = sum(values) / len(values)

    if average >= 1:
        return "صعودی 🟢"

    if average <= -1:
        return "نزولی 🔴"

    return "خنثی ⚪"


def format_percent(value):
    if value is None:
        return "داده کافی نیست"

    if value > 0:
        return f"🟢 +{value:.2f}%"

    if value < 0:
        return f"🔴 {value:.2f}%"

    return "⚪ 0.00%"


def analyze_market(
    prices,
    history
):
    gold_6h = historical_change(
        history,
        prices["gold18"],
        "gold18",
        6
    )

    gold_24h = historical_change(
        history,
        prices["gold18"],
        "gold18",
        24
    )

    gold_72h = historical_change(
        history,
        prices["gold18"],
        "gold18",
        72
    )

    coin_24h = historical_change(
        history,
        prices["coin"],
        "coin",
        24
    )

    dollar_24h = historical_change(
        history,
        prices["dollar"],
        "dollar",
        24
    )

    gold_trend = determine_trend([
        gold_6h,
        gold_24h,
        gold_72h,
    ])

    coin_trend = determine_trend([
        coin_24h
    ])

    dollar_trend = determine_trend([
        dollar_24h
    ])

    positive = 0
    negative = 0

    for value in [
        gold_24h,
        coin_24h,
        dollar_24h,
    ]:
        if value is not None:
            if value > 0.3:
                positive += 1
            elif value < -0.3:
                negative += 1

    if positive >= 2:
        conclusion = (
            "تمایل کلی بازار در ۲۴ ساعت اخیر "
            "مثبت و متمایل به صعود بوده است."
        )

    elif negative >= 2:
        conclusion = (
            "تمایل کلی بازار در ۲۴ ساعت اخیر "
            "منفی و متمایل به نزول بوده است."
        )

    else:
        conclusion = (
            "بازار در مجموع در وضعیت متعادل "
            "یا نوسانی قرار دارد."
        )

    return {
        "gold_6h": gold_6h,
        "gold_24h": gold_24h,
        "gold_72h": gold_72h,
        "coin_24h": coin_24h,
        "dollar_24h": dollar_24h,
        "gold_trend": gold_trend,
        "coin_trend": coin_trend,
        "dollar_trend": dollar_trend,
        "conclusion": conclusion,
    }


# =========================
# FORECAST
# =========================

def build_forecast(
    prices,
    analysis
):
    gold_24h = analysis["gold_24h"]
    gold_72h = analysis["gold_72h"]
    dollar_24h = analysis["dollar_24h"]

    score = 0

    for value, weight in [
        (gold_24h, 2),
        (gold_72h, 1),
        (dollar_24h, 1),
    ]:
        if value is None:
            continue

        if value > 0.5:
            score += weight

        elif value < -0.5:
            score -= weight

    if score >= 2:
        main_scenario = "سناریوی غالب: صعودی 🟢"

    elif score <= -2:
        main_scenario = "سناریوی غالب: نزولی 🔴"

    else:
        main_scenario = "سناریوی غالب: خنثی / نوسانی ⚪"

    bullish = (
        "در صورت ادامه رشد طلا و دلار و عبور "
        "از مقاومت، احتمال ادامه حرکت صعودی بیشتر می‌شود."
    )

    neutral = (
        "در صورت نوسان محدود قیمت‌ها بین حمایت و مقاومت، "
        "احتمال ادامه حرکت نوسانی بیشتر است."
    )

    bearish = (
        "در صورت شکست حمایت و کاهش همزمان طلا یا دلار، "
        "ریسک ادامه افت قیمت افزایش پیدا می‌کند."
    )

    return {
        "main": main_scenario,
        "bullish": bullish,
        "neutral": neutral,
        "bearish": bearish,
    }


# =========================
# CHANGE TEXT
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

    return "⚪ ➖ بدون تغییر"


# =========================
# HOURLY MESSAGE
# =========================

def build_hourly_message(
    prices,
    previous_prices
):
    info = get_date_info()

    update_time = info["now"].strftime(
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


# =========================
# DAILY MESSAGE
# =========================

def build_daily_message(
    prices,
    history
):
    info = get_date_info()

    analysis = analyze_market(
        prices,
        history
    )

    forecast = build_forecast(
        prices,
        analysis
    )

    gold_support, gold_resistance = get_real_levels(
        history,
        "gold18",
        prices["gold18"]
    )

    coin_support, coin_resistance = get_real_levels(
        history,
        "coin",
        prices["coin"]
    )

    occasions = get_today_occasions()

    history_count = len(history)

    return f"""🌙✨ زرین ماه
📊 گزارش روزانه بازار طلا، سکه و دلار

━━━━━━━━━━━━━━━━━━

📅 {info["weekday"]}
🗓 تاریخ شمسی: {info["jalali"]}
📆 تاریخ میلادی: {info["gregorian"]}

🎉 مناسبت‌های امروز:
{occasions}

━━━━━━━━━━━━━━━━━━

💰 قیمت‌های فعلی

🟡 طلای ۱۸ عیار
{prices["gold18"]:,} تومان

🪙 سکه امامی
{prices["coin"]:,} تومان

💵 دلار آزاد
{prices["dollar"]:,} تومان

━━━━━━━━━━━━━━━━━━

📈 تحلیل بازار

🟡 طلای ۱۸ عیار
۶ ساعت: {format_percent(analysis["gold_6h"])}
۲۴ ساعت: {format_percent(analysis["gold_24h"])}
۷۲ ساعت: {format_percent(analysis["gold_72h"])}
روند: {analysis["gold_trend"]}

🪙 سکه امامی
۲۴ ساعت: {format_percent(analysis["coin_24h"])}
روند: {analysis["coin_trend"]}

💵 دلار آزاد
۲۴ ساعت: {format_percent(analysis["dollar_24h"])}
روند: {analysis["dollar_trend"]}

📌 جمع‌بندی:
{analysis["conclusion"]}

━━━━━━━━━━━━━━━━━━

🎯 حمایت و مقاومت

🟡 طلای ۱۸ عیار
حمایت: {gold_support:,} تومان
مقاومت: {gold_resistance:,} تومان

🪙 سکه امامی
حمایت: {coin_support:,} تومان
مقاومت: {coin_resistance:,} تومان

━━━━━━━━━━━━━━━━━━

🔮 چشم‌انداز کوتاه‌مدت

{forecast["main"]}

🟢 سناریوی صعودی:
{forecast["bullish"]}

⚪ سناریوی خنثی:
{forecast["neutral"]}

🔴 سناریوی نزولی:
{forecast["bearish"]}

━━━━━━━━━━━━━━━━━━

⏰ یادآوری امروز

بازار طلا و ارز می‌تواند در طول روز
با سرعت زیادی تغییر کند.
برای تصمیم‌گیری، قیمت لحظه‌ای و
شرایط بازار را دوباره بررسی کنید.

⚠️ این تحلیل صرفاً احتمالی و بر اساس
داده‌های ثبت‌شده بازار است و به هیچ عنوان
توصیه قطعی خرید یا فروش نیست.

📊 تعداد داده‌های تاریخی استفاده‌شده:
{history_count}

📚 منبع قیمت‌ها: TGJU

━━━━━━━━━━━━━━━━━━

🌙 زرین ماه
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""


# =========================
# TELEGRAM
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
        "disable_web_page_preview": True,
    }

    max_attempts = 5

    for attempt in range(
        1,
        max_attempts + 1
    ):
        try:
            response = requests.post(
                url,
                data=data,
                timeout=30,
            )

            if response.ok:
                result = response.json()

                if result.get("ok"):
                    print(
                        "Telegram message sent "
                        f"successfully on attempt "
                        f"{attempt}."
                    )

                    return result

                print(
                    "Telegram API rejected request:"
                )
                print(result)

            else:
                print(
                    f"Telegram HTTP error "
                    f"{response.status_code}: "
                    f"{response.text}"
                )

        except requests.RequestException as error:
            print(
                f"Telegram connection error "
                f"on attempt {attempt}: {error}"
            )

        if attempt < max_attempts:
            wait_seconds = attempt * 10

            print(
                f"Retrying Telegram in "
                f"{wait_seconds} seconds..."
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        "ارسال پیام به تلگرام پس از "
        "۵ تلاش ناموفق بود."
    )


# =========================
# MAIN
# =========================

def main():
    print(
        f"Starting ZarinMah bot "
        f"in mode: {BOT_MODE}"
    )

    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    previous_prices = load_previous_prices()
    history = load_history()

    print("Fetching current prices...")

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

    print("Current prices:")
    print(prices)

    # ثبت snapshot جدید
    updated_history = add_history_record(
        history,
        prices
    )

    if BOT_MODE == "daily":
        message = build_daily_message(
            prices,
            updated_history
        )

    else:
        message = build_hourly_message(
            prices,
            previous_prices
        )

    print(
        f"Sending {BOT_MODE} message..."
    )

    # اول ارسال
    send_to_telegram(message)

    # فقط بعد از ارسال موفق ذخیره کن
    save_current_prices(prices)
    save_history(updated_history)

    print(
        "Bot completed successfully."
    )


if __name__ == "__main__":
    main()
