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


def to_persian_digits(value):
    table = str.maketrans(
        "0123456789",
        "۰۱۲۳۴۵۶۷۸۹",
    )
    return str(value).translate(table)


def load_send_status():
    if not os.path.exists(STATUS_FILE):
        return {
            "hourly": {},
            "daily": {},
            "watchdog": {},
        }

    try:
        with open(
            STATUS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            data = {}

        data.setdefault("hourly", {})
        data.setdefault("daily", {})
        data.setdefault("watchdog", {})

        return data

    except Exception as error:
        print(
            "Could not load send status:",
            repr(error),
        )

        return {
            "hourly": {},
            "daily": {},
            "watchdog": {},
        }


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


def is_daily_sent_today(slot):
    status = load_send_status()

    daily = status.get(
        "daily",
        {},
    )

    if not isinstance(daily, dict):
        return False

    return (
        daily.get("slot") == slot
        and daily.get("telegram") is True
        and daily.get("eitaa") is True
    )


def save_daily_telegram_status(slot):
    status = load_send_status()

    daily = status.get(
        "daily",
        {},
    )

    if not isinstance(daily, dict):
        daily = {}

    daily["slot"] = slot
    daily["telegram"] = True
    daily.setdefault(
        "eitaa",
        False,
    )
    daily["updated_at"] = datetime.now(
        TEHRAN
    ).isoformat()

    status["daily"] = daily

    save_send_status(status)


def get_today_info():
    now = datetime.now(TEHRAN)

    jalali = jdatetime.datetime.fromgregorian(
        datetime=now
    )

    date_text = (
        f"{jalali.day} "
        f"{PERSIAN_MONTHS[jalali.month - 1]} "
        f"{jalali.year}"
    )

    return {
        "now": now,
        "jalali": jalali,
        "weekday": WEEKDAYS[now.weekday()],
        "date_text": to_persian_digits(
            date_text
        ),
    }


def get_occasions(today):
    try:
        response = requests.get(
            OCCASIONS_URL,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        jalali = today["jalali"]

        result = []

        for item in data:
            date = item.get(
                "date",
                {},
            )

            if date.get("type") != "shamsi":
                continue

            values = date.get(
                "date",
                [],
            )

            if len(values) < 2:
                continue

            try:
                day = int(values[0])
            except (
                ValueError,
                TypeError,
            ):
                continue

            month_name = values[1]

            event_name = item.get(
                "event_name",
                "",
            ).strip()

            if not event_name:
                continue

            if (
                day == jalali.day
                and month_name
                == PERSIAN_MONTHS[
                    jalali.month - 1
                ]
            ):
                if event_name not in result:
                    result.append(
                        event_name
                    )

        return result[:1]

    except Exception as error:
        print(
            "Could not load occasions:",
            repr(error),
        )
        return []


def percent_change(
    current,
    previous,
):
    if current is None or previous is None:
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

    return to_persian_digits(
        f"{int(number):,}"
        if number.is_integer()
        else f"{number:,.2f}"
    )


def format_change(value):
    if value is None:
        return "—"

    sign = "+" if value > 0 else ""

    return to_persian_digits(
        f"{sign}{value:.2f}%"
    )


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

    values = [
        value
        for value in [
            gold,
            coin,
            dollar,
        ]
        if value is not None
    ]

    positive = sum(
        1
        for value in values
        if value > 0.20
    )

    negative = sum(
        1
        for value in values
        if value < -0.20
    )

    if positive >= 2:
        market = "📊 بازار: متمایل به صعود"

    elif negative >= 2:
        market = "📊 بازار: متمایل به نزول"

    else:
        market = "📊 بازار: نوسانی"

    if gold is not None and gold > 0.50:
        buyer = (
            "🛍 خرید: قبل از تصمیم، "
            "چند نرخ اخیر را مقایسه کنید."
        )

    elif gold is not None and gold < -0.50:
        buyer = (
            "🛍 خرید: کاهش اخیر را با "
            "چند نرخ اخیر بررسی کنید."
        )

    else:
        buyer = (
            "🛍 خرید: قیمت، وزن و اجرت را "
            "همزمان بررسی کنید."
        )

    return {
        "gold": gold,
        "coin": coin,
        "dollar": dollar,
        "market": market,
        "buyer": buyer,
    }


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
            + occasions[0]
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

{analysis["market"]}

{analysis["buyer"]}

🌙 @ZarinMahGold"""

    return message.strip()


def save_daily_message(message):
    with open(
        DAILY_MESSAGE_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        file.write(message)

    print(
        "Daily message saved."
    )

    print(
        "Message length:",
        len(message),
    )


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
        "Telegram HTTP:",
        response.status_code,
    )

    print(
        "Telegram response:",
        response.text,
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram error: {data}"
        )

    return True


def main():
    now = datetime.now(TEHRAN)

    current_slot = now.strftime(
        "%Y-%m-%d"
    )

    manual_run = (
        os.environ.get(
            "SCHEDULED_RUN"
        )
        != "true"
    )

    print(
        "==================================="
    )

    print(
        "ZarinMah Daily Analysis"
    )

    print(
        "Tehran:",
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    print(
        "Manual run:",
        manual_run,
    )

    print(
        "==================================="
    )

    # در اجرای زمان‌بندی‌شده:
    # اگر هر دو مقصد قبلاً ارسال شده‌اند، کاری نکن.
    #
    # در اجرای دستی:
    # همیشه دوباره ارسال کن.

    if (
        not manual_run
        and is_daily_sent_today(
            current_slot
        )
    ):
        print(
            "Daily analysis already sent today."
        )
        return

    message = build_message()

    print(
        "Generated daily message:"
    )

    print(
        message
    )

    save_daily_message(
        message
    )

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
        "Telegram daily analysis sent."
    )

    print(
        "Daily analysis file is ready for Eitaa."
    )

    print(
        "Daily analysis preparation completed."
    )


if __name__ == "__main__":
    main()
