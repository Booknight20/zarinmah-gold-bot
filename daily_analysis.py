```python
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import jdatetime
import requests

from bot import (
    get_all_prices,
    load_previous_prices,
)


# =========================
# تنظیمات
# =========================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL = "@ZarinMahGold"

TEHRAN = ZoneInfo("Asia/Tehran")

STATUS_FILE = "send_status.json"

OCCASIONS_URL = (
    "https://raw.githubusercontent.com/"
    "BaseMax/persian-holidays-api/master/holidays.json"
)

WEEKDAYS = [
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

GREGORIAN_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


# =========================
# وضعیت ارسال
# =========================

def load_send_status():
    if not os.path.exists(STATUS_FILE):
        return {
            "hourly": {},
            "daily": {},
        }

    try:
        with open(
            STATUS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return {
                "hourly": {},
                "daily": {},
            }

        data.setdefault("hourly", {})
        data.setdefault("daily", {})

        return data

    except Exception as error:
        print(
            "Could not load send status:",
            error,
        )

        return {
            "hourly": {},
            "daily": {},
        }


def save_daily_send_status(slot):
    status = load_send_status()

    status["daily"] = {
        "slot": slot,
        "sent_at": datetime.now(
            TEHRAN
        ).isoformat(),
    }

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

    print(
        "Daily send status saved:",
        slot,
    )


# =========================
# تبدیل اعداد به فارسی
# =========================

def to_persian_digits(value):
    table = str.maketrans(
        "0123456789",
        "۰۱۲۳۴۵۶۷۸۹",
    )

    return str(value).translate(table)


# =========================
# تاریخ امروز
# =========================

def get_today_info():
    now = datetime.now(TEHRAN)

    jalali = jdatetime.datetime.fromgregorian(
        datetime=now
    )

    weekday = WEEKDAYS[now.weekday()]

    date_text = (
        f"{jalali.day} "
        f"{PERSIAN_MONTHS[jalali.month - 1]} "
        f"{jalali.year}"
    )

    date_text = to_persian_digits(date_text)

    return {
        "now": now,
        "jalali": jalali,
        "weekday": weekday,
        "date_text": date_text,
    }


# =========================
# دریافت مناسبت‌های امروز
# =========================

def get_occasions(today):
    jalali = today["jalali"]
    now = today["now"]

    occasions = []

    try:
        response = requests.get(
            OCCASIONS_URL,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        for item in data:
            date = item.get("date", {})
            date_type = date.get("type")
            date_values = date.get("date", [])
            event_name = item.get(
                "event_name",
                "",
            ).strip()

            if not event_name:
                continue

            # مناسبت‌های شمسی
            if date_type == "shamsi":
                if len(date_values) >= 2:
                    try:
                        day = int(date_values[0])
                    except ValueError:
                        continue

                    month_name = date_values[1]

                    if (
                        day == jalali.day
                        and month_name
                        == PERSIAN_MONTHS[
                            jalali.month - 1
                        ]
                    ):
                        occasions.append(
                            event_name
                        )

            # مناسبت‌های میلادی
            elif date_type == "gregorian":
                if len(date_values) >= 2:
                    try:
                        day = int(date_values[0])
                    except ValueError:
                        continue

                    month_name = date_values[1]

                    current_month_name = (
                        GREGORIAN_MONTHS[
                            now.month - 1
                        ]
                    )

                    if (
                        day == now.day
                        and month_name
                        == current_month_name
                    ):
                        occasions.append(
                            event_name
                        )

        # حذف موارد تکراری
        unique = []

        for occasion in occasions:
            if occasion not in unique:
                unique.append(occasion)

        return unique

    except Exception as error:
        print(
            "Could not load occasions:",
            error,
        )

        return []


# =========================
# محاسبه درصد تغییر
# =========================

def percent_change(current, previous):
    if previous is None or previous == 0:
        return None

    return (
        (current - previous)
        / previous
    ) * 100


# =========================
# وضعیت روند
# =========================

def trend_label(change_percent):
    if change_percent is None:
        return "نامشخص"

    if change_percent > 0.20:
        return "صعودی"

    if change_percent < -0.20:
        return "نزولی"

    return "نوسانی / تقریباً خنثی"


# =========================
# ساخت تحلیل
# =========================

def build_analysis(prices, previous):
    previous = previous or {}

    gold_old = previous.get("gold18")
    coin_old = previous.get("coin")
    dollar_old = previous.get("dollar")

    gold_pct = percent_change(
        prices["gold18"],
        gold_old,
    )

    coin_pct = percent_change(
        prices["coin"],
        coin_old,
    )

    dollar_pct = percent_change(
        prices["dollar"],
        dollar_old,
    )

    gold_trend = trend_label(gold_pct)
    coin_trend = trend_label(coin_pct)
    dollar_trend = trend_label(dollar_pct)

    parts = []

    # -------------------------
    # روند کلی
    # -------------------------

    available_changes = [
        value
        for value in [
            gold_pct,
            coin_pct,
            dollar_pct,
        ]
        if value is not None
    ]

    if available_changes:

        positive = sum(
            1
            for value in available_changes
            if value > 0.20
        )

        negative = sum(
            1
            for value in available_changes
            if value < -0.20
        )

        if positive >= 2:

            parts.append(
                "در آخرین ثبت‌های قیمتی، "
                "جهت کلی بازار متمایل به صعود بوده است."
            )

        elif negative >= 2:

            parts.append(
                "در آخرین ثبت‌های قیمتی، "
                "جهت کلی بازار متمایل به نزول بوده است."
            )

        else:

            parts.append(
                "حرکت قیمت‌ها یکدست نیست و "
                "بازار در وضعیت نوسانی قرار دارد."
            )

    else:

        parts.append(
            "برای مقایسه روند، "
            "داده قبلی کافی در دسترس نیست."
        )

    # -------------------------
    # طلا و دلار
    # -------------------------

    if (
        gold_pct is not None
        and dollar_pct is not None
    ):

        if (
            gold_pct > 0
            and dollar_pct > 0
        ):

            parts.append(
                "طلای ۱۸ عیار و دلار "
                "در یک جهت حرکت کرده‌اند."
            )

        elif (
            gold_pct < 0
            and dollar_pct < 0
        ):

            parts.append(
                "طلای ۱۸ عیار و دلار "
                "هر دو کاهش داشته‌اند."
            )

        else:

            parts.append(
                "بین حرکت طلا و دلار "
                "هم‌جهتی کاملی دیده نمی‌شود."
            )

    # -------------------------
    # سکه نسبت به طلا
    # -------------------------

    if (
        coin_pct is not None
        and gold_pct is not None
    ):

        if coin_pct > gold_pct + 0.20:

            parts.append(
                "سکه امامی نسبت به طلای ۱۸ عیار "
                "حرکت قوی‌تری داشته است."
            )

        elif coin_pct < gold_pct - 0.20:

            parts.append(
                "حرکت سکه امامی از طلای ۱۸ عیار "
                "ضعیف‌تر بوده است."
            )

        else:

            parts.append(
                "حرکت سکه و طلای ۱۸ عیار "
                "تقریباً هم‌جهت بوده است."
            )

    # -------------------------
    # نکته خریدار
    # -------------------------

    if (
        gold_pct is not None
        and gold_pct > 0.5
    ):

        buyer_note = (
            "با توجه به رشد اخیر قیمت، "
            "خریدار بهتر است قبل از تصمیم، "
            "چند نرخ متوالی را مقایسه کند."
        )

    elif (
        gold_pct is not None
        and gold_pct < -0.5
    ):

        buyer_note = (
            "با توجه به کاهش اخیر، "
            "مقایسه چند نرخ متوالی و "
            "بررسی روند قبل از خرید اهمیت دارد."
        )

    else:

        buyer_note = (
            "در بازار نوسانی، "
            "مقایسه چند نرخ متوالی و توجه به "
            "اجرت و وزن محصول اهمیت بیشتری دارد."
        )

    return {
        "gold_pct": gold_pct,
        "coin_pct": coin_pct,
        "dollar_pct": dollar_pct,
        "gold_trend": gold_trend,
        "coin_trend": coin_trend,
        "dollar_trend": dollar_trend,
        "summary": " ".join(parts),
        "buyer_note": buyer_note,
    }


# =========================
# قالب پیام
# =========================

def build_message():
    today = get_today_info()

    prices = get_all_prices()

    previous = load_previous_prices()

    occasions = get_occasions(today)

    analysis = build_analysis(
        prices,
        previous,
    )

    if occasions:

        occasion_text = "\n".join(
            f"🎉 {item}"
            for item in occasions[:5]
        )

    else:

        occasion_text = (
            "🎉 مناسبت ویژه‌ای در داده تقویم پیدا نشد."
        )

    def change_text(value):

        if value is None:
            return "بدون داده قبلی"

        sign = "+" if value > 0 else ""

        return (
            f"{sign}{value:.2f}%"
        )

    gold_change = change_text(
        analysis["gold_pct"]
    )

    coin_change = change_text(
        analysis["coin_pct"]
    )

    dollar_change = change_text(
        analysis["dollar_pct"]
    )

    return f"""🌙✨ زرین ماه | تحلیل روزانه بازار

📅 {today["weekday"]} | {today["date_text"]}

{occasion_text}

━━━━━━━━━━━━━━━━━━

💰 وضعیت امروز بازار

🟡 طلای ۱۸ عی
```
