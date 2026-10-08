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
TELEGRAM_CHANNEL = "@ZarinMahGold"

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
# ابزارهای کمکی
# =========================================================

def to_persian_digits(value):
    table = str.maketrans(
        "0123456789",
        "۰۱۲۳۴۵۶۷۸۹",
    )

    return str(value).translate(table)


def format_price(value):
    if value is None:
        return "نامشخص"

    try:
        number = float(value)
    except (ValueError, TypeError):
        return str(value)

    if number.is_integer():
        text = f"{int(number):,}"
    else:
        text = f"{number:,.2f}"

    return to_persian_digits(text)


def format_percent(value):
    if value is None:
        return "—"

    sign = "+" if value > 0 else ""

    return to_persian_digits(
        f"{sign}{value:.2f}%"
    )


def percent_change(current, previous):
    if current is None:
        return None

    if previous is None:
        return None

    try:
        current = float(current)
        previous = float(previous)
    except (ValueError, TypeError):
        return None

    if previous == 0:
        return None

    return (
        (current - previous)
        / previous
    ) * 100


# =========================================================
# وضعیت ارسال
# =========================================================

def load_send_status():
    default_status = {
        "hourly": {},
        "daily": {},
        "watchdog": {},
        "daily_telegram": {},
        "daily_eitaa": {},
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
            data = {}

        for key, value in default_status.items():
            data.setdefault(key, value)

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


def destination_sent_today(
    status,
    destination,
    slot,
):
    key = f"daily_{destination}"

    record = status.get(
        key,
        {},
    )

    if not isinstance(record, dict):
        return False

    return (
        record.get("slot")
        == slot
    )


def save_daily_destination_status(
    destination,
    slot,
):
    status = load_send_status()

    key = f"daily_{destination}"

    status[key] = {
        "slot": slot,
        "sent_at": datetime.now(
            TEHRAN
        ).isoformat(),
    }

    save_send_status(status)

    print(
        f"Daily {destination} status saved:",
        slot,
    )


def mark_daily_complete(slot):
    status = load_send_status()

    status["daily"] = {
        "slot": slot,
        "sent_at": datetime.now(
            TEHRAN
        ).isoformat(),
    }

    save_send_status(status)

    print(
        "Daily send status saved:",
        slot,
    )


# =========================================================
# تاریخ
# =========================================================

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
        "weekday": WEEKDAYS[
            now.weekday()
        ],
        "date_text": to_persian_digits(
            date_text
        ),
    }


# =========================================================
# مناسبت‌های امروز
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

            values = date.get(
                "date",
                [],
            )

            event_name = item.get(
                "event_name",
                "",
            ).strip()

            if not event_name:
                continue

            if len(values) < 2:
                continue

            try:
                day = int(values[0])
            except (ValueError, TypeError):
                continue

            month_name = values[1]

            if date_type == "shamsi":

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
# تحلیل
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

    half = percent_change(
        prices.get("half"),
        previous.get("half"),
    )

    quarter = percent_change(
        prices.get("quarter"),
        previous.get("quarter"),
    )

    dollar = percent_change(
        prices.get("dollar"),
        previous.get("dollar"),
    )

    all_changes = [
        value
        for value in [
            gold,
            coin,
            half,
            quarter,
            dollar,
        ]
        if value is not None
    ]

    positive = sum(
        1
        for value in all_changes
        if value > 0.20
    )

    negative = sum(
        1
        for value in all_changes
        if value < -0.20
    )

    neutral = sum(
        1
        for value in all_changes
        if -0.20 <= value <= 0.20
    )

    if not all_changes:
        market = (
            "بازار: داده قبلی کافی نیست."
        )

    elif positive >= 3:
        market = (
            "بازار: کفه حرکت‌های صعودی سنگین‌تر است."
        )

    elif negative >= 3:
        market = (
            "بازار: کفه حرکت‌های نزولی سنگین‌تر است."
        )

    else:
        market = (
            "بازار: حرکت قیمت‌ها یکدست نیست و "
            "شرایط نوسانی است."
        )

    changes = {
        "طلای ۱۸ عیار": gold,
        "سکه": coin,
        "نیم‌سکه": half,
        "ربع‌سکه": quarter,
        "دلار": dollar,
    }

    valid_changes = [
        (name, value)
        for name, value in changes.items()
        if value is not None
    ]

    if valid_changes:
        strongest_name, strongest_value = max(
            valid_changes,
            key=lambda item: abs(item[1]),
        )

        strongest = (
            f"بیشترین تغییر: {strongest_name} "
            f"{format_percent(strongest_value)}"
        )

    else:
        strongest = (
            "بیشترین تغییر: داده کافی نیست."
        )

    if (
        gold is not None
        and dollar is not None
    ):
        if (
            gold > 0.20
            and dollar > 0.20
        ):
            gold_dollar = (
                "طلا و دلار در یک جهت صعودی حرکت کرده‌اند."
            )

        elif (
            gold < -0.20
            and dollar < -0.20
        ):
            gold_dollar = (
                "طلا و دلار هر دو کاهش داشته‌اند."
            )

        elif (
            (gold > 0.20 and dollar < -0.20)
            or
            (gold < -0.20 and dollar > 0.20)
        ):
            gold_dollar = (
                "بین حرکت طلا و دلار واگرایی کوتاه‌مدت دیده می‌شود."
            )

        else:
            gold_dollar = (
                "حرکت طلا و دلار نسبتاً کم‌نوسان بوده است."
            )
    else:
        gold_dollar = (
            "برای مقایسه طلا و دلار داده کافی نیست."
        )

    if (
        coin is not None
        and gold is not None
    ):
        difference = coin - gold

        if difference > 0.30:
            coin_gold = (
                "سکه نسبت به طلا حرکت قوی‌تری داشته است."
            )

        elif difference < -0.30:
            coin_gold = (
                "سکه نسبت به طلا حرکت ضعیف‌تری داشته است."
            )

        else:
            coin_gold = (
                "سکه و طلا تقریباً هم‌جهت حرکت کرده‌اند."
            )
    else:
        coin_gold = (
            "برای مقایسه سکه و طلا داده کافی نیست."
        )

    if all_changes:
        average_change = (
            sum(
                abs(value)
                for value in all_changes
            )
            / len(all_changes)
        )
    else:
        average_change = None

    if average_change is None:
        volatility = (
            "شدت نوسان قابل محاسبه نیست."
        )

    elif average_change >= 1.0:
        volatility = (
            "نوسان بازار نسبتاً قابل‌توجه بوده است."
        )

    elif average_change >= 0.30:
        volatility = (
            "بازار نوسان متوسط داشته است."
        )

    else:
        volatility = (
            "حرکت قیمت‌ها نسبتاً آرام بوده است."
        )

    if (
        gold is not None
        and gold > 0.50
    ):
        buyer = (
            "خریدار: چند نرخ اخیر، وزن و اجرت "
            "را قبل از خرید مقایسه کند."
        )

    elif (
        gold is not None
        and gold < -0.50
    ):
        buyer = (
            "خریدار: کاهش اخیر را با چند نرخ "
            "متوالی و اجرت محصول مقایسه کند."
        )

    else:
        buyer = (
            "خریدار: قیمت روز، وزن و اجرت "
            "را همزمان بررسی کند."
        )

    return {
        "gold": gold,
        "coin": coin,
        "half": half,
        "quarter": quarter,
        "dollar": dollar,
        "market": market,
        "strongest": strongest,
        "gold_dollar": gold_dollar,
        "coin_gold": coin_gold,
        "volatility": volatility,
        "buyer": buyer,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
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

    if occasions:
        occasion_text = (
            "🎉 "
            + " | ".join(occasions)
        )
    else:
        occasion_text = ""

    message = f"""🌙✨ زرین ماه | تحلیل روزانه

📅 {today["weekday"]} | {today["date_text"]}
{occasion_text}

💰 قیمت‌ها

🟡 طلا: {format_price(prices.get("gold18"))} تومان | {format_percent(analysis["gold"])}
🪙 سکه: {format_price(prices.get("coin"))} تومان | {format_percent(analysis["coin"])}
🪙 نیم‌سکه: {format_price(prices.get("half"))} تومان
🪙 ربع‌سکه: {format_price(prices.get("quarter"))} تومان
💵 دلار: {format_price(prices.get("dollar"))} تومان | {format_percent(analysis["dollar"])}

📊 {analysis["market"]}
📌 صعودی: {to_persian_digits(analysis["positive"])} | نزولی: {to_persian_digits(analysis["negative"])} | خنثی: {to_persian_digits(analysis["neutral"])}

🔎 {analysis["strongest"]}
🔗 {analysis["gold_dollar"]}
🪙 {analysis["coin_gold"]}
📈 {analysis["volatility"]}

🛍 {analysis["buyer"]}

📌 مبنا: مقایسه با آخرین قیمت ذخیره‌شده قبلی ربات.
این متن تحلیل خودکار است و پیش‌بینی قطعی بازار نیست.

🌙 زرین ماه
📲 @ZarinMahGold
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
        "chat_id": TELEGRAM_CHANNEL,
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
        "Telegram daily analysis sent successfully."
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
        "Daily message saved to:",
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

    telegram_sent = destination_sent_today(
        status,
        "telegram",
        current_slot,
    )

    eitaa_sent = destination_sent_today(
        status,
        "eitaa",
        current_slot,
    )

    daily_complete = (
        telegram_sent
        and eitaa_sent
    )

    if (
        scheduled_run
        and daily_complete
    ):
        print(
            "Daily analysis already sent "
            "to Telegram and Eitaa for:",
            current_slot,
        )
        return

    # حتی اگر تلگرام قبلاً فرستاده شده باشد،
    # پیام جدید را می‌سازیم تا ایتا بتواند آن را retry کند.
    message = build_message()

    print(
        "Generated daily analysis:"
    )

    print(message)

    save_daily_message(
        message
    )

    # -----------------------------------------------------
    # تلگرام
    # -----------------------------------------------------

    if telegram_sent:
        print(
            "Telegram already sent for:",
            current_slot,
        )

    else:
        print(
            "Sending daily analysis to Telegram..."
        )

        send_to_telegram(
            message
        )

        save_daily_destination_status(
            "telegram",
            current_slot,
        )

        telegram_sent = True

    # -----------------------------------------------------
    # ایتا
    # -----------------------------------------------------
    #
    # ایتا در این فایل ارسال نمی‌شود.
    # فایل send_daily_eitaa.py بعد از این مرحله
    # همان daily_message.txt را مستقیماً ارسال می‌کند.
    # -----------------------------------------------------

    print(
        "Daily message is ready for Eitaa."
    )

    print(
        "Daily analysis preparation completed."
    )


if __name__ == "__main__":
    main()
