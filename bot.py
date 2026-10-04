import os
import re
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# ==========================================
# تنظیمات
# ==========================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
BOT_MODE = os.environ.get("BOT_MODE", "hourly")

CHANNEL = "@ZarinMahGold"

TEHRAN = ZoneInfo("Asia/Tehran")

PREVIOUS_FILE = "previous_prices.json"
HISTORY_FILE = "market_history.json"

MAX_HISTORY_DAYS = 30

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
# اعداد فارسی / عربی
# ==========================================

def normalize_digits(text):

    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )

    return text.translate(table)


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

            value = match.group(1)
            value = value.replace(",", "")

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
# دریافت تمام قیمت‌ها
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
# previous_prices.json
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
            f"⚠️ خطا در خواندن previous_prices: {error}"
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

    print(
        "✅ previous_prices.json ذخیره شد."
    )


# ==========================================
# market_history.json
# ==========================================

def load_market_history():

    if not os.path.exists(HISTORY_FILE):

        print(
            "⚪ market_history.json وجود ندارد."
        )

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
            f"⚠️ خطا در خواندن تاریخچه: {error}"
        )

        return []


def save_market_history(history):

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

    print(
        f"✅ تاریخچه ذخیره شد: {len(history)} رکورد"
    )


def add_history_record(history, prices):

    now = datetime.now(TEHRAN)

    record = {
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
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

    cleaned = []

    for item in history:

        try:

            item_time = datetime.fromisoformat(
                item["timestamp"]
            )

            if item_time >= cutoff:

                cleaned.append(item)

        except Exception:

            continue

    cleaned.sort(
        key=lambda x: x["timestamp"]
    )

    return cleaned


# ==========================================
# تبدیل تاریخ میلادی به شمسی
# ==========================================

def gregorian_to_jalali(gy, gm, gd):

    g_days_in_month = [
        31, 28, 31, 30, 31, 30,
        31, 31, 30, 31, 30, 31
    ]

    j_days_in_month = [
        31, 31, 31, 31, 31, 31,
        30, 30, 30, 30, 30, 30,
        29
    ]

    gy2 = gy - 1600

    if gy2 >= 0:
        gy_calc = gy2
    else:
        gy_calc = gy2 - 1

    days = (
        365 * gy_calc
        + (gy_calc + 3) // 4
        - (gy_calc + 99) // 100
        + (gy_calc + 399) // 400
    )

    for i in range(gm - 1):
        days += g_days_in_month[i]

    if (
        gm > 2
        and gy % 4 == 0
        and (
            gy % 100 != 0
            or gy % 400 == 0
        )
    ):
        days += 1

    days += gd - 1
    days -= 79

    j_np = days // 12053
    days %= 12053

    jy = 979 + 33 * j_np

    jy += 4 * (days // 1461)

    days %= 1461

    if days > 365:

        jy += (days - 1) // 365
        days = (days - 1) % 365

    for i in range(12):

        if days < j_days_in_month[i]:

            jm = i + 1
            jd = days + 1

            return jy, jm, jd

        days -= j_days_in_month[i]

    return jy, 12, 30


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
# مناسبت‌ها
# ==========================================

OCCASIONS = {

    (1, 1): "نوروز و آغاز سال نو",
    (1, 2): "عید نوروز",
    (1, 3): "عید نوروز",
    (1, 4): "عید نوروز",
    (1, 12): "روز جمهوری اسلامی ایران",
    (1, 13): "روز طبیعت",

    (2, 12): "روز معلم",

    (3, 14): "رحلت امام خمینی (ره)",
    (3, 15): "قیام ۱۵ خرداد",

    (5, 11): "روز ملی صنعت و معدن",

    (6, 1): "روز پزشک",

    (7, 1): "آغاز سال تحصیلی",
    (7, 20): "روز بزرگداشت حافظ",

    (8, 13): "روز دانش‌آموز",

    (9, 16): "روز دانشجو",

    (11, 22): "پیروزی انقلاب اسلامی",

    (12, 29): "روز ملی شدن صنعت نفت",
}


def get_occasion(jm, jd):

    occasion = OCCASIONS.get(
        (jm, jd)
    )

    if occasion:

        return (
            f"🎉 مناسبت امروز: {occasion}"
        )

    return (
        "📅 مناسبت ویژه‌ای برای امروز "
        "در تقویم ثابت ربات ثبت نشده است."
    )


# ==========================================
# تغییر درصدی
# ==========================================

def percent_change(current, old):

    if old is None:
        return None

    if old == 0:
        return None

    return (
        (current - old) / old
    ) * 100


def format_percent(value):

    if value is None:
        return "نامشخص"

    sign = "+" if value > 0 else ""

    return f"{sign}{value:.2f}%"


# ==========================================
# پیدا کردن قیمت نزدیک به زمان مورد نظر
# ==========================================

def find_oldest_before(
    history,
    target_time
):

    candidates = []

    for item in history:

        try:

            item_time = datetime.fromisoformat(
                item["timestamp"]
            )

            if item_time <= target_time:
                candidates.append(item)

        except Exception:

            continue

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x["timestamp"]
    )

    return candidates[-1]


# ==========================================
# محاسبه بازدهی تاریخی
# ==========================================

def historical_change(
    history,
    current_price,
    key,
    hours
):

    now = datetime.now(TEHRAN)

    target = now - timedelta(
        hours=hours
    )

    old_record = find_oldest_before(
        history,
        target
    )

    if not old_record:
        return None

    old_price = old_record.get(key)

    if not old_price:
        return None

    return percent_change(
        current_price,
        old_price
    )


# ==========================================
# پیدا کردن رکوردهای یک بازه
# ==========================================

def get_window_records(
    history,
    hours
):

    now = datetime.now(TEHRAN)

    start = now - timedelta(
        hours=hours
    )

    result = []

    for item in history:

        try:

            item_time = datetime.fromisoformat(
                item["timestamp"]
            )

            if (
                start
                <= item_time
                <= now
            ):

                result.append(item)

        except Exception:

            continue

    return result


# ==========================================
# سقف و کف واقعی تاریخچه
# ==========================================

def get_high_low(
    history,
    key,
    hours
):

    records = get_window_records(
        history,
        hours
    )

    values = []

    for item in records:

        value = item.get(key)

        if isinstance(value, (int, float)):

            values.append(value)

    if not values:
        return None, None

    return max(values), min(values)


# ==========================================
# حمایت / مقاومت بر اساس تاریخچه
# ==========================================

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

    if len(values) < 3:

        # اگر تاریخچه هنوز کم است
        # فقط یک محدوده بسیار تقریبی
        return (
            int(current_price * 0.99),
            int(current_price * 1.01)
        )

    values.sort()

    # سه سطح پایین‌تر از قیمت
    lower = [
        x for x in values
        if x < current_price
    ]

    # سه سطح بالاتر از قیمت
    upper = [
        x for x in values
        if x > current_price
    ]

    if lower:

        support = max(lower)

    else:

        support = min(values)

    if upper:

        resistance = min(upper)

    else:

        resistance = max(values)

    return (
        int(support),
        int(resistance)
    )


# ==========================================
# تشخیص روند
# ==========================================

def determine_trend(
    history,
    prices,
    key
):

    changes = []

    for hours in [
        6,
        24,
        72
    ]:

        change = historical_change(
            history,
            prices[key],
            key,
            hours
        )

        if change is not None:

            changes.append(
                change
            )

    if not changes:

        return (
            "نامشخص",
            None
        )

    average = sum(changes) / len(
        changes
    )

    if average >= 1:

        return (
            "صعودی",
            average
        )

    if average <= -1:

        return (
            "نزولی",
            average
        )

    return (
        "خنثی / نوسانی",
        average
    )


# ==========================================
# تحلیل واقعی بازار
# ==========================================

def analyze_market(
    history,
    prices
):

    if len(history) < 3:

        return (
            "📊 تحلیل بازار\n\n"
            "⚠️ هنوز تاریخچه کافی جمع نشده است.\n"
            "بعد از چند ساعت فعالیت ربات، "
            "تحلیل روند دقیق‌تر خواهد شد."
        )

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

    gold_trend, _ = determine_trend(
        history,
        prices,
        "gold18"
    )

    dollar_trend, _ = determine_trend(
        history,
        prices,
        "dollar"
    )

    coin_trend, _ = determine_trend(
        history,
        prices,
        "coin"
    )

    lines = [
        "📊 تحلیل مبتنی بر تاریخچه بازار",
        "",
        f"🟡 طلای ۱۸ عیار:",
        f"۶ ساعت: {format_percent(gold_6h)}",
        f"۲۴ ساعت: {format_percent(gold_24h)}",
        f"۷۲ ساعت: {format_percent(gold_72h)}",
        "",
        f"🪙 سکه امامی ۲۴ ساعت:",
        f"{format_percent(coin_24h)}",
        "",
        f"💵 دلار آزاد ۲۴ ساعت:",
        f"{format_percent(dollar_24h)}",
        "",
        "📌 روند فعلی:",
        f"طلا: {gold_trend}",
        f"سکه: {coin_trend}",
        f"دلار: {dollar_trend}",
    ]

    # تشخیص هم‌جهتی
    positive = 0
    negative = 0

    for value in [
        gold_24h,
        coin_24h,
        dollar_24h
    ]:

        if value is not None:

            if value > 0.3:
                positive += 1

            elif value < -0.3:
                negative += 1

    if positive >= 2:

        conclusion = (
            "🟢 جمع‌بندی: مومنتوم کوتاه‌مدت "
            "بازار متمایل به صعود است."
        )

    elif negative >= 2:

        conclusion = (
            "🔴 جمع‌بندی: مومنتوم کوتاه‌مدت "
            "بازار متمایل به نزول است."
        )

    else:

        conclusion = (
            "🟡 جمع‌بندی: بازار در وضعیت "
            "خنثی/نوسانی قرار دارد."
        )

    lines.extend([
        "",
        conclusion
    ])

    return "\n".join(lines)


# ==========================================
# پیش‌بینی سناریویی
# ==========================================

def build_forecast(
    history,
    prices
):

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

    dollar_24h = historical_change(
        history,
        prices["dollar"],
        "dollar",
        24
    )

    if gold_24h is None:

        return (
            "🔮 سناریوی کوتاه‌مدت\n\n"
            "برای ارائه سناریوی معتبرتر، "
            "ابتدا باید تاریخچه بیشتری جمع شود."
        )

    momentum = gold_24h

    if gold_72h is not None:

        momentum = (
            gold_24h * 0.65
            + gold_72h * 0.35
        )

    if (
        dollar_24h is not None
        and dollar_24h > 0.5
    ):

        momentum += 0.25

    elif (
        dollar_24h is not None
        and dollar_24h < -0.5
    ):

        momentum -= 0.25

    if momentum >= 1:

        main_scenario = (
            "🟢 سناریوی صعودی"
        )

        detail = (
            "روند تاریخی کوتاه‌مدت مثبت است. "
            "در صورت حفظ رشد دلار و تداوم تقاضا، "
            "احتمال ادامه حرکت صعودی بیشتر می‌شود."
        )

    elif momentum <= -1:

        main_scenario = (
            "🔴 سناریوی نزولی"
        )

        detail = (
            "روند تاریخی کوتاه‌مدت منفی است. "
            "در صورت تداوم افت دلار و فشار فروش، "
            "احتمال ادامه اصلاح افزایش می‌یابد."
        )

    else:

        main_scenario = (
            "🟡 سناریوی خنثی / نوسانی"
        )

        detail = (
            "روند کوتاه‌مدت سیگنال قدرتمندی "
            "در یک جهت نشان نمی‌دهد و نوسان "
            "در محدوده فعلی محتمل‌تر است."
        )

    return (
        "🔮 سناریوی کوتاه‌مدت\n\n"
        f"{main_scenario}\n"
        f"{detail}\n\n"
        "سناریوی صعودی:\n"
        "عبور از سقف‌های اخیر و افزایش تقاضا "
        "می‌تواند حرکت صعودی را تقویت کند.\n\n"
        "سناریوی خنثی:\n"
        "تثبیت دلار و کاهش نوسان می‌تواند "
        "قیمت را در محدوده فعلی نگه دارد.\n\n"
        "سناریوی نزولی:\n"
        "شکست کف‌های اخیر و افت دلار می‌تواند "
        "باعث افزایش فشار اصلاحی شود."
    )


# ==========================================
# پیام ساعتی
# ==========================================

def build_hourly_message(
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
# پیام روزانه
# ==========================================

def build_daily_message(
    prices,
    previous_prices,
    history
):

    now = datetime.now(TEHRAN)

    jy, jm, jd = gregorian_to_jalali(
        now.year,
        now.month,
        now.day
    )

    weekday = WEEKDAYS[
        now.weekday()
    ]

    month_name = JALALI_MONTHS[jm]

    gregorian_date = now.strftime(
        "%Y/%m/%d"
    )

    support, resistance = get_real_levels(
        history,
        "gold18",
        prices["gold18"]
    )

    occasion = get_occasion(
        jm,
        jd
    )

    analysis = analyze_market(
        history,
        prices
    )

    forecast = build_forecast(
        history,
        prices
    )

    history_count = len(history)

    return f"""🌙✨ زرین ماه
☀️ گزارش ویژه روزانه بازار

━━━━━━━━━━━━━━━━━━

📅 تاریخ امروز

{weekday}
📆 {jd} {month_name} {jy}
🗓 میلادی: {gregorian_date}

{occasion}

━━━━━━━━━━━━━━━━━━

💎 قیمت‌های فعلی

🟡 طلای ۱۸ عیار
💰 {prices["gold18"]:,} تومان

🪙 سکه امامی
💰 {prices["coin"]:,} تومان

💵 دلار آزاد
💰 {prices["dollar"]:,} تومان

━━━━━━━━━━━━━━━━━━

{analysis}

━━━━━━━━━━━━━━━━━━

📈 محدوده‌های مهم طلای ۱۸ عیار

🟢 حمایت تاریخی نزدیک:
{support:,} تومان

🔴 مقاومت تاریخی نزدیک:
{resistance:,} تومان

📌 این سطوح از روی قیمت‌های ثبت‌شده
در تاریخچه اخیر ربات محاسبه شده‌اند.

━━━━━━━━━━━━━━━━━━

{forecast}

━━━━━━━━━━━━━━━━━━

💡 یادآوری امروز

در بازار ایران، دلار، اونس جهانی،
اخبار اقتصادی و سیاسی و میزان تقاضا
می‌توانند باعث تغییر سریع قیمت طلا شوند.

━━━━━━━━━━━━━━━━━━

⚠️ سلب مسئولیت

این تحلیل بر اساس داده‌های تاریخی
ثبت‌شده توسط ربات و شرایط فعلی بازار
تهیه شده و صرفاً احتمالی است.

این محتوا توصیه قطعی برای خرید یا
فروش طلا، سکه یا ارز نیست.

━━━━━━━━━━━━━━━━━━

📊 منبع قیمت‌ها: TGJU
📚 تعداد رکوردهای تاریخچه: {history_count}

🕚 گزارش روزانه: ساعت ۱۱:۰۰ تهران

🌙 زرین ماه
✨ ویترین طلای کم‌اجرت

📲 @ZarinMahGold
"""


# ==========================================
# متن تغییر قیمت
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
            f"🟢 ▲ +{difference:,} تومان"
        )

    if difference < 0:

        return (
            f"🔴 ▼ {difference:,} تومان"
        )

    return "⚪ ➖ بدون تغییر"


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
        "disable_web_page_preview": True,
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
            f"Telegram API error: {response.text}"
        )

    result = response.json()

    if not result.get("ok"):

        raise RuntimeError(
            f"Telegram API error: {result}"
        )

    print(
        "✅ پیام با موفقیت ارسال شد."
    )


# ==========================================
# اجرای اصلی
# ==========================================

def main():

    print("================================")
    print("🌙 ZarinMah Gold Bot")
    print(f"Mode: {BOT_MODE}")
    print("================================")

    previous_prices = load_previous_prices()

    history = load_market_history()

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

    # --------------------------------------
    # ثبت قیمت جدید در تاریخچه
    # --------------------------------------

    history = add_history_record(
        history,
        prices
    )

    # --------------------------------------
    # ساخت پیام
    # --------------------------------------

    if BOT_MODE == "daily":

        message = build_daily_message(
            prices,
            previous_prices,
            history
        )

    else:

        message = build_hourly_message(
            prices,
            previous_prices
        )

    print("\n----- پیام نهایی -----")
    print(message)
    print("----------------------\n")

    # --------------------------------------
    # ابتدا تلگرام
    # --------------------------------------

    send_to_telegram(message)

    # --------------------------------------
    # سپس ذخیره فایل‌ها
    # --------------------------------------

    save_current_prices(
        prices
    )

    save_market_history(
        history
    )


if __name__ == "__main__":
    main()
