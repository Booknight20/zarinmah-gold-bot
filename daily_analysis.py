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


# =========================================================
# تنظیمات
# =========================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL = "@ZarinMahGold"

TEHRAN = ZoneInfo("Asia/Tehran")

STATUS_FILE = "send_status.json"
DAILY_MESSAGE_FILE = "daily_message.txt"

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


# =========================================================
# اعداد فارسی
# =========================================================

def to_persian_digits(value):
    table = str.maketrans(
        "0123456789",
        "۰۱۲۳۴۵۶۷۸۹",
    )

    return str(value).translate(table)


# =========================================================
# وضعیت ارسال
# =========================================================

def load_send_status():
    default_status = {
        "hourly": {},
        "daily": {},
        "watchdog": {},
    }

    if not os.path.exists(STATUS_FILE):
        return default_status

    try:
        with open(
            STATUS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return default_status

        data.setdefault("hourly", {})
        data.setdefault("daily", {})
        data.setdefault("watchdog", {})

        return data

    except Exception as error:
        print(
            "Could not load send status:",
            repr(error),
        )

        return default_status


def save_send_status(status):
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


def get_daily_status(status, slot):
    daily = status.get("daily", {})

    if not isinstance(daily, dict):
        daily = {}

    if daily.get("slot") != slot:
        return {
            "slot": slot,
            "telegram": False,
        }

    return {
        "slot": slot,
        "telegram": bool(
            daily.get("telegram", False)
        ),
    }


def save_daily_telegram_status(slot):
    status = load_send_status()

    current = get_daily_status(
        status,
        slot,
    )

    current["slot"] = slot
    current["telegram"] = True
    current["sent_at"] = datetime.now(
        TEHRAN
    ).isoformat()

    status["daily"] = current

    save_send_status(status)

    print(
        "Daily telegram status saved:",
        slot,
    )


# =========================================================
# تاریخ امروز
# =========================================================

def get_today_info():
    now = datetime.now(TEHRAN)

    jalali = jdatetime.datetime.fromgregorian(
        datetime=now
    )

    weekday = WEEKDAYS[
        now.weekday()
    ]

    date_text = (
        f"{jalali.day} "
        f"{PERSIAN_MONTHS[jalali.month - 1]} "
        f"{jalali.year}"
    )

    return {
        "now": now,
        "jalali": jalali,
        "weekday": weekday,
        "date_text": to_persian_digits(
            date_text
        ),
    }


# =========================================================
# مناسبت امروز
# =========================================================

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
            date = item.get(
                "date",
                {},
            )

            date_type = date.get(
                "type"
            )

            date_values = date.get(
                "date",
                [],
            )

            event_name = item.get(
                "event_name",
                "",
            ).strip()

            if not event_name:
                continue

            if date_type == "shamsi":

                if len(date_values) < 2:
                    continue

                try:
                    day = int(
                        date_values[0]
                    )
                except (
                    ValueError,
                    TypeError,
                ):
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

            elif date_type == "gregorian":

                if len(date_values) < 2:
                    continue

                try:
                    day = int(
                        date_values[0]
                    )
                except (
                    ValueError,
                    TypeError,
                ):
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

        unique = []

        for item in occasions:
            if item not in unique:
                unique.append(item)

        return unique[:2]

    except Exception as error:
        print(
            "Could not load occasions:",
            repr(error),
        )

        return []


# =========================================================
# درصد تغییر
# =========================================================

def percent_change(
    current,
    previous,
):
    if current is None:
        return None

    if previous is None:
        return None

    try:
        current = float(current)
        previous = float(previous)
    except (
        ValueError,
        TypeError,
    ):
        return None

    if previous == 0:
        return None

    return (
        (current - previous)
        / previous
    ) * 100


# =========================================================
# فرمت قیمت
# =========================================================

def format_price(value):
    if value is None:
        return "نامشخص"

    try:
        number = float(value)
    except (
        ValueError,
        TypeError,
    ):
        return str(value)

    if number.is_integer():
        text = f"{int(number):,}"
    else:
        text = f"{number:,.2f}"

    return to_persian_digits(text)


# =========================================================
# فرمت درصد
# =========================================================

def format_change(value):
    if value is None:
        return "—"

    sign = "+" if value > 0 else ""

    text = (
        f"{sign}"
        f"{value:.2f}%"
    )

    return to_persian_digits(text)


# =========================================================
# ساخت تحلیل کوتاه
# =========================================================

def build_analysis(
    prices,
    previous,
):
    previous = previous or {}

    gold = percent_change(
        prices.get("gold18"),
        previous.get("gold18"),
    )

    coin = percent_change(
        prices.get("coin"),
        previous.get("coin"),
    )

    dollar = percent_change(
        prices.get("dollar"),
        previous.get("dollar"),
    )

    changes = {
        "طلای ۱۸ عیار": gold,
        "سکه": coin,
        "دلار": dollar,
    }

    valid = [
        (name, value)
        for name, value in changes.items()
        if value is not None
    ]

    if not valid:
        direction = (
            "📊 روند: "
            "داده قبلی کافی نیست."
        )

        strongest = ""

    else:
        positive = sum(
            1
            for _, value in valid
            if value > 0.20
        )

        negative = sum(
            1
            for _, value in valid
            if value < -0.20
        )

        if positive >= 2:
            direction = (
                "📊 بازار: متمایل به صعود"
            )

        elif negative >= 2:
            direction = (
                "📊 بازار: متمایل به نزول"
            )

        else:
            direction = (
                "📊 بازار: نوسانی"
            )

        strongest_name, strongest_value = max(
            valid,
            key=lambda item: abs(item[1]),
        )

        strongest = (
            f"🔎 بیشترین تغییر: "
            f"{strongest_name} "
            f"{format_change(strongest_value)}"
        )

    if (
        gold is not None
        and gold > 0.50
    ):
        buyer = (
            "🛍 خرید: قبل از تصمیم، "
            "چند نرخ متوالی را مقایسه کنید."
        )

    elif (
        gold is not None
        and gold < -0.50
    ):
        buyer = (
            "🛍 خرید: کاهش اخیر را با "
            "چند نرخ متوالی بررسی کنید."
        )

    else:
        buyer = (
            "🛍 خرید: اجرت و وزن محصول را "
            "در کنار قیمت روز بررسی کنید."
        )

    return {
        "gold": gold,
        "coin": coin,
        "dollar": dollar,
        "direction": direction,
        "strongest": strongest,
        "buyer": buyer,
    }


# =========================================================
# ساخت پیام کوتاه
# =========================================================

def build_message():

    today = get_today_info()

    prices = get_all_prices()

    if not prices:
        raise RuntimeError(
            "No price data received."
        )

    previous = load_previous_prices()

    analysis = build_analysis(
        prices,
        previous,
    )

    occasions = get_occasions(
        today
    )

    occasion_text = ""

    if occasions:
        occasion_text = (
            "\n🎉 "
            + " | ".join(occasions)
            + "\n"
        )

    message = f"""🌙 زرین ماه | تحلیل روزانه

📅 {today["weekday"]} | {today["date_text"]}
{occasion_text}
🟡 طلا: {format_price(prices.get("gold18"))} تومان
   تغییر: {format_change(analysis["gold"])} 

🪙 سکه: {format_price(prices.get("coin"))} تومان
   تغییر: {format_change(analysis["coin"])}

🪙 نیم‌سکه: {format_price(prices.get("half"))} تومان

🪙 ربع‌سکه: {format_price(prices.get("quarter"))} تومان

💵 دلار: {format_price(prices.get("dollar"))} تومان
   تغییر: {format_change(analysis["dollar"])}

{analysis["direction"]}
{analysis["strongest"]}

{analysis["buyer"]}

🌙 @ZarinMahGold
"""

    return message.strip()


# =========================================================
# ارسال تلگرام
# =========================================================

def send_to_telegram(message):

    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing."
        )

    url = (
        "https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": CHANNEL,
        "text": message,
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30,
    )

    print(
        "Telegram HTTP status:",
        response.status_code,
    )

    print(
        "Telegram response:",
        response.text,
    )

    if response.status_code != 200:
        response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram returned an error: {data}"
        )

    print(
        "Daily analysis sent to Telegram."
    )

    return True


# =========================================================
# ذخیره پیام برای ایتا
# =========================================================

def save_daily_message(message):

    with open(
        DAILY_MESSAGE_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        file.write(message)

    print(
        "Daily message saved:",
        DAILY_MESSAGE_FILE,
    )

    print(
        "Daily message length:",
        len(message),
        "characters",
    )


# =========================================================
# اجرای اصلی
# =========================================================

def main():

    now = datetime.now(TEHRAN)

    current_slot = now.strftime(
        "%Y-%m-%d"
    )

    scheduled_run = (
        os.environ.get(
            "SCHEDULED_RUN"
        )
        == "true"
    )

    watchdog_retry = (
        os.environ.get(
            "WATCHDOG_RETRY"
        )
        == "true"
    )

    print(
        "==================================="
    )

    print(
        "ZarinMah Daily Analysis"
    )

    print(
        "Tehran time:",
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    print(
        "Scheduled run:",
        scheduled_run,
    )

    print(
        "Watchdog retry:",
        watchdog_retry,
    )

    print(
        "==================================="
    )

    status = load_send_status()

    daily_status = get_daily_status(
        status,
        current_slot,
    )

    telegram_sent = daily_status[
        "telegram"
    ]

    message = build_message()

    print(
        "Generated short daily analysis:"
    )

    print(
        message
    )

    # همیشه فایل جدید ساخته می‌شود
    # تا ایتا همان پیام جدید را دریافت کند.
    save_daily_message(
        message
    )

    if telegram_sent:

        print(
            "Telegram already sent for:",
            current_slot,
        )

        print(
            "Skipping duplicate Telegram send."
        )

    else:

        print(
            "Sending daily analysis to Telegram..."
        )

        send_to_telegram(
            message
        )

        save_daily_telegram_status(
            current_slot
        )

    print(
        "Daily analysis preparation completed."
    )


if __name__ == "__main__":
    main()
