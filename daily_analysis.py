import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import jdatetime
import requests

from bot import (
    get_all_prices,
    load_previous_prices,
    send_to_telegram,
    send_to_eitaa,
)


# =========================================================
# تنظیمات
# =========================================================

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

ASSET_LABELS = {
    "gold18": "طلای ۱۸ عیار",
    "coin": "سکه امامی",
    "half": "نیم‌سکه",
    "quarter": "ربع‌سکه",
    "dollar": "دلار آزاد",
}

ASSET_EMOJIS = {
    "gold18": "🟡",
    "coin": "🪙",
    "half": "🪙",
    "quarter": "🪙",
    "dollar": "💵",
}


# =========================================================
# وضعیت ارسال
# =========================================================

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
            error,
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


def save_daily_destination_status(
    slot,
    destination,
):
    status = load_send_status()

    status[f"daily_{destination}"] = {
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
# تبدیل اعداد
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
        return "بدون داده قبلی"

    sign = "+" if value > 0 else ""

    return to_persian_digits(
        f"{sign}{value:.2f}%"
    )


# =========================================================
# تاریخ امروز
# =========================================================

def get_today_info():
    now = datetime.now(TEHRAN)

    jalali = jdatetime.datetime.fromgregorian(
        datetime=now
    )

    return {
        "now": now,
        "jalali": jalali,
        "weekday": WEEKDAYS[now.weekday()],
        "date_text": to_persian_digits(
            f"{jalali.day} "
            f"{PERSIAN_MONTHS[jalali.month - 1]} "
            f"{jalali.year}"
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

            if (
                not event_name
                or len(values) < 2
            ):
                continue

            try:
                day = int(
                    values[0]
                )
            except (
                ValueError,
                TypeError,
            ):
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

        return unique

    except Exception as error:
        print(
            "Could not load occasions:",
            error,
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

    if (
        previous is None
        or previous == 0
    ):
        return None

    return (
        (current - previous)
        / previous
    ) * 100


# =========================================================
# روند
# =========================================================

def trend_label(value):
    if value is None:
        return "داده کافی نیست"

    if value > 0.20:
        return "صعودی"

    if value < -0.20:
        return "نزولی"

    return "نوسانی / خنثی"


def direction_text(value):
    if value is None:
        return "⚪ بدون داده قبلی"

    if value > 0.20:
        return "🟢 افزایش"

    if value < -0.20:
        return "🔴 کاهش"

    return "🟡 نوسان محدود"


# =========================================================
# تحلیل بازار
# =========================================================

def build_analysis(
    prices,
    previous,
):
    previous = previous or {}

    changes = {
        asset: percent_change(
            prices.get(asset),
            previous.get(asset),
        )
        for asset in ASSET_LABELS
    }

    available = [
        value
        for value in changes.values()
        if value is not None
    ]

    positive = sum(
        1
        for value in available
        if value > 0.20
    )

    negative = sum(
        1
        for value in available
        if value < -0.20
    )

    neutral = sum(
        1
        for value in available
        if -0.20 <= value <= 0.20
    )

    # -----------------------------------------------------
    # جهت کلی بازار
    # -----------------------------------------------------

    if not available:

        market_direction = (
            "داده قبلی کافی برای تشخیص "
            "جهت بازار وجود ندارد."
        )

    elif positive >= 3:

        market_direction = (
            "در آخرین مقایسه، کفه "
            "حرکت‌های صعودی سنگین‌تر است."
        )

    elif negative >= 3:

        market_direction = (
            "در آخرین مقایسه، کفه "
            "حرکت‌های نزولی سنگین‌تر است."
        )

    else:

        market_direction = (
            "حرکت دارایی‌ها یکدست نیست "
            "و بازار در وضعیت نوسانی است."
        )

    # -----------------------------------------------------
    # قوی‌ترین حرکت
    # -----------------------------------------------------

    strongest_asset = None
    strongest_value = None

    for asset, value in changes.items():

        if value is None:
            continue

        if (
            strongest_value is None
            or abs(value)
            > abs(strongest_value)
        ):
            strongest_asset = asset
            strongest_value = value

    gold_change = changes["gold18"]
    dollar_change = changes["dollar"]
    coin_change = changes["coin"]

    # -----------------------------------------------------
    # رابطه طلا و دلار
    # -----------------------------------------------------

    if (
        gold_change is not None
        and dollar_change is not None
    ):

        if (
            gold_change > 0.20
            and dollar_change > 0.20
        ):

            gold_dollar = (
                "طلا و دلار در یک جهت "
                "صعودی حرکت کرده‌اند."
            )

        elif (
            gold_change < -0.20
            and dollar_change < -0.20
        ):

            gold_dollar = (
                "طلا و دلار هر دو کاهش داشته‌اند."
            )

        elif (
            (
                gold_change > 0.20
                and dollar_change < -0.20
            )
            or (
                gold_change < -0.20
                and dollar_change > 0.20
            )
        ):

            gold_dollar = (
                "بین حرکت طلا و دلار "
                "واگرایی کوتاه‌مدت دیده می‌شود."
            )

        else:

            gold_dollar = (
                "حرکت طلا و دلار نسبتاً "
                "کم‌نوسان یا ترکیبی بوده است."
            )

    else:

        gold_dollar = (
            "برای مقایسه طلا و دلار "
            "داده کافی نیست."
        )

    # -----------------------------------------------------
    # رابطه سکه و طلا
    # -----------------------------------------------------

    if (
        coin_change is not None
        and gold_change is not None
    ):

        gap = (
            coin_change
            - gold_change
        )

        if gap > 0.30:

            coin_gold = (
                "سکه امامی نسبت به طلای "
                "۱۸ عیار حرکت قوی‌تری داشته است."
            )

        elif gap < -0.30:

            coin_gold = (
                "سکه امامی نسبت به طلای "
                "۱۸ عیار حرکت ضعیف‌تری داشته است."
            )

        else:

            coin_gold = (
                "حرکت سکه امامی و طلای "
                "۱۸ عیار تقریباً هم‌جهت بوده است."
            )

    else:

        coin_gold = (
            "برای مقایسه سکه و طلا "
            "داده کافی نیست."
        )

    # -----------------------------------------------------
    # شدت نوسان
    # -----------------------------------------------------

    if available:

        average_abs_change = (
            sum(
                abs(value)
                for value in available
            )
            / len(available)
        )

    else:

        average_abs_change = None

    if average_abs_change is None:

        volatility = (
            "شدت نوسان قابل محاسبه نیست."
        )

    elif average_abs_change >= 1.0:

        volatility = (
            "دامنه حرکت قیمت‌ها "
            "نسبتاً قابل‌توجه بوده است."
        )

    elif average_abs_change >= 0.30:

        volatility = (
            "بازار نوسان متوسطی داشته است."
        )

    else:

        volatility = (
            "حرکت قیمت‌ها در محدوده "
            "نسبتاً آرامی بوده است."
        )

    # -----------------------------------------------------
    # نکته برای خریدار
    # -----------------------------------------------------

    if (
        gold_change is not None
        and gold_change > 0.50
    ):

        buyer_note = (
            "با توجه به رشد اخیر، بهتر است "
            "چند نرخ متوالی، وزن، اجرت و "
            "قیمت نهایی محصول با هم بررسی شوند."
        )

    elif (
        gold_change is not None
        and gold_change < -0.50
    ):

        buyer_note = (
            "با توجه به کاهش اخیر، مقایسه "
            "چند نرخ متوالی و بررسی اجرت و "
            "وزن برای تصمیم خرید مهم است."
        )

    else:

        buyer_note = (
            "در بازار کم‌نوسان یا متغیر، "
            "مقایسه نرخ لحظه‌ای با اجرت و "
            "وزن محصول اهمیت بیشتری دارد."
        )

    return {
        "changes": changes,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "market_direction": market_direction,
        "strongest_asset": strongest_asset,
        "strongest_value": strongest_value,
        "gold_dollar": gold_dollar,
        "coin_gold": coin_gold,
        "volatility": volatility,
        "buyer_note": buyer_note,
    }


# =========================================================
# ساخت پیام
# =========================================================

def build_message():

    today = get_today_info()

    prices = get_all_prices()

    if not prices:
        raise RuntimeError(
            "No price data received."
        )

    previous = load_previous_prices()

    occasions = get_occasions(
        today
    )

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
            "🎉 امروز مناسبت ثبت‌شده‌ای "
            "در داده تقویم پیدا نشد."
        )

    # -----------------------------------------------------
    # قیمت‌ها
    # -----------------------------------------------------

    price_lines = []

    for asset in [
        "gold18",
        "coin",
        "half",
        "quarter",
        "dollar",
    ]:

        change = (
            analysis["changes"][
                asset
            ]
        )

        price_lines.append(
            f'{ASSET_EMOJIS[asset]} '
            f'{ASSET_LABELS[asset]}: '
            f'{format_price(prices.get(asset))} تومان'
        )

        price_lines.append(
            f'   {direction_text(change)} | '
            f'{format_percent(change)}'
        )

    # -----------------------------------------------------
    # قوی‌ترین حرکت
    # -----------------------------------------------------

    if (
        analysis["strongest_asset"]
        is not None
        and analysis["strongest_value"]
        is not None
    ):

        strongest_text = (
            f'قوی‌ترین حرکت مربوط به '
            f'{ASSET_LABELS[analysis["strongest_asset"]]} '
            f'با {format_percent(analysis["strongest_value"])} بوده است.'
        )

    else:

        strongest_text = (
            "قوی‌ترین حرکت قابل مشاهده مشخص نیست."
        )

    # -----------------------------------------------------
    # شمارش صعود/نزول
    # -----------------------------------------------------

    count_text = (
        f'🟢 صعودی: '
        f'{to_persian_digits(analysis["positive"])}  |  '
        f'🔴 نزولی: '
        f'{to_persian_digits(analysis["negative"])}  |  '
        f'🟡 خنثی: '
        f'{to_persian_digits(analysis["neutral"])}'
    )

    return f"""🌙✨ زرین ماه | تحلیل روزانه بازار

📅 {today["weekday"]} | {today["date_text"]}

{occasion_text}

━━━━━━━━━━━━━━━━━━

💰 وضعیت قیمت‌ها

{chr(10).join(price_lines)}

━━━━━━━━━━━━━━━━━━

📊 نبض بازار

{analysis["market_direction"]}

{count_text}

{strongest_text}

━━━━━━━━━━━━━━━━━━

🔎 طلا و دلار

{analysis["gold_dollar"]}

━━━━━━━━━━━━━━━━━━

🪙 سکه و طلا

{analysis["coin_gold"]}

━━━━━━━━━━━━━━━━━━

📈 شدت نوسان

{analysis["volatility"]}

━━━━━━━━━━━━━━━━━━

🛍 نکته برای خریداران

{analysis["buyer_note"]}

━━━━━━━━━━━━━━━━━━

📌 مبنای تحلیل

تغییرات نسبت به آخرین قیمت ذخیره‌شده قبلی ربات محاسبه شده است.
این متن تحلیل خودکار داده‌های قیمت است و پیش‌بینی قطعی بازار نیست.

━━━━━━━━━━━━━━━━━━

🌙 زرین ماه
«ویترین طلای کم‌اجرت»

📲 @ZarinMahGold
"""


# =========================================================
# اجرای اصلی
# =========================================================

def main():

    now = datetime.now(
        TEHRAN
    )

    current_slot = (
        now.strftime(
            "%Y-%m-%d"
        )
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
        "ZarinMah Daily Market Analysis"
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

    telegram_sent = (
        status
        .get(
            "daily_telegram",
            {},
        )
        .get(
            "slot"
        )
        == current_slot
    )

    eitaa_sent = (
        status
        .get(
            "daily_eitaa",
            {},
        )
        .get(
            "slot"
        )
        == current_slot
    )

    daily_complete = (
        status
        .get(
            "daily",
            {},
        )
        .get(
            "slot"
        )
        == current_slot
    )

    if daily_complete:

        print(
            "Daily analysis already sent "
            "to all destinations for:",
            current_slot,
        )

        return

    # -----------------------------------------------------
    # ساخت تحلیل
    # -----------------------------------------------------

    message = build_message()

    print(
        "Generated daily analysis:"
    )

    print(
        message
    )

    # -----------------------------------------------------
    # تلگرام
    # -----------------------------------------------------

    if not telegram_sent:

        print(
            "Sending daily analysis "
            "to Telegram..."
        )

        send_to_telegram(
            message
        )

        save_daily_destination_status(
            current_slot,
            "telegram",
        )

        telegram_sent = True

        print(
            "Daily analysis sent to Telegram."
        )

    else:

        print(
            "Daily analysis already sent "
            "to Telegram for:",
            current_slot,
        )

    # -----------------------------------------------------
    # ایتا
    # -----------------------------------------------------

    if not eitaa_sent:

        print(
            "Sending daily analysis "
            "to Eitaa..."
        )

        send_to_eitaa(
            message
        )

        save_daily_destination_status(
            current_slot,
            "eitaa",
        )

        eitaa_sent = True

        print(
            "Daily analysis sent to Eitaa."
        )

    else:

        print(
            "Daily analysis already sent "
            "to Eitaa for:",
            current_slot,
        )

    # -----------------------------------------------------
    # تکمیل ارسال
    # -----------------------------------------------------

    if (
        telegram_sent
        and eitaa_sent
    ):

        mark_daily_complete(
            current_slot
        )

        print(
            "Daily analysis completed "
            "on Telegram + Eitaa."
        )


# =========================================================
# اجرا
# =========================================================

if __name__ == "__main__":
    main()
