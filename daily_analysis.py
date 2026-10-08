import json
import os
import time
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
EITAAYAR_TOKEN = os.environ.get("EITAAYAR_TOKEN")
EITAA_CHAT_ID = os.environ.get("EITAA_CHAT_ID")

TELEGRAM_CHANNEL = "@ZarinMahGold"

TEHRAN = ZoneInfo("Asia/Tehran")

STATUS_FILE = "send_status.json"

OCCASIONS_URL = (
    "https://raw.githubusercontent.com/"
    "BaseMax/persian-holidays-api/master/holidays.json"
)

EITAA_API_URL = (
    "https://eitaayar.ir/api/"
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
# تبدیل اعداد
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
            "eitaa": False,
        }

    return {
        "slot": slot,
        "telegram": bool(
            daily.get("telegram", False)
        ),
        "eitaa": bool(
            daily.get("eitaa", False)
        ),
    }


def save_daily_destination_status(
    slot,
    destination,
):
    status = load_send_status()

    current = get_daily_status(
        status,
        slot,
    )

    current[destination] = True
    current["slot"] = slot
    current["sent_at"] = datetime.now(
        TEHRAN
    ).isoformat()

    status["daily"] = current

    save_send_status(status)

    print(
        f"Daily {destination} status saved:",
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
# مناسبت‌ها
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

            # شمسی
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

            # میلادی
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

        for occasion in occasions:
            if occasion not in unique:
                unique.append(
                    occasion
                )

        return unique

    except Exception as error:
        print(
            "Could not load occasions:",
            repr(error),
        )

        return []


# =========================================================
# محاسبه درصد تغییر
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
# روند
# =========================================================

def trend_label(change_percent):
    if change_percent is None:
        return "نامشخص"

    if change_percent > 0.20:
        return "صعودی"

    if change_percent < -0.20:
        return "نزولی"

    return "نوسانی / تقریباً خنثی"


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

def change_text(value):
    if value is None:
        return "بدون داده قبلی"

    sign = "+" if value > 0 else ""

    text = (
        f"{sign}"
        f"{value:.2f}%"
    )

    return to_persian_digits(text)


# =========================================================
# تحلیل بازار
# =========================================================

def build_analysis(
    prices,
    previous,
):
    previous = previous or {}

    gold_pct = percent_change(
        prices.get("gold18"),
        previous.get("gold18"),
    )

    coin_pct = percent_change(
        prices.get("coin"),
        previous.get("coin"),
    )

    half_pct = percent_change(
        prices.get("half"),
        previous.get("half"),
    )

    quarter_pct = percent_change(
        prices.get("quarter"),
        previous.get("quarter"),
    )

    dollar_pct = percent_change(
        prices.get("dollar"),
        previous.get("dollar"),
    )

    changes = {
        "gold18": gold_pct,
        "coin": coin_pct,
        "half": half_pct,
        "quarter": quarter_pct,
        "dollar": dollar_pct,
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

    if not available:
        market_direction = (
            "برای مقایسه روند، "
            "داده قبلی کافی در دسترس نیست."
        )

    elif positive >= 3:
        market_direction = (
            "در آخرین ثبت‌های قیمتی، "
            "جهت کلی بازار متمایل به صعود "
            "بوده است."
        )

    elif negative >= 3:
        market_direction = (
            "در آخرین ثبت‌های قیمتی، "
            "جهت کلی بازار متمایل به نزول "
            "بوده است."
        )

    else:
        market_direction = (
            "حرکت قیمت‌ها یکدست نیست و "
            "بازار در وضعیت نوسانی قرار دارد."
        )

    # قوی‌ترین حرکت
    strongest_asset = None
    strongest_value = None

    for name, value in changes.items():
        if value is None:
            continue

        if (
            strongest_value is None
            or abs(value) > abs(strongest_value)
        ):
            strongest_asset = name
            strongest_value = value

    asset_labels = {
        "gold18": "طلای ۱۸ عیار",
        "coin": "سکه امامی",
        "half": "نیم‌سکه",
        "quarter": "ربع‌سکه",
        "dollar": "دلار",
    }

    if (
        strongest_asset is not None
        and strongest_value is not None
    ):
        strongest_text = (
            f"{asset_labels[strongest_asset]} "
            f"با تغییر "
            f"{change_text(strongest_value)} "
            f"بیشترین نوسان ثبت‌شده را داشته است."
        )
    else:
        strongest_text = (
            "برای تعیین بیشترین نوسان، "
            "داده کافی در دسترس نیست."
        )

    # طلا و دلار
    if (
        gold_pct is not None
        and dollar_pct is not None
    ):
        if (
            gold_pct > 0
            and dollar_pct > 0
        ):
            gold_dollar_text = (
                "طلای ۱۸ عیار و دلار "
                "در یک جهت حرکت کرده‌اند."
            )

        elif (
            gold_pct < 0
            and dollar_pct < 0
        ):
            gold_dollar_text = (
                "طلای ۱۸ عیار و دلار "
                "هر دو کاهش داشته‌اند."
            )

        else:
            gold_dollar_text = (
                "بین حرکت طلا و دلار "
                "هم‌جهتی کاملی دیده نمی‌شود."
            )

    else:
        gold_dollar_text = (
            "برای مقایسه حرکت طلا و دلار "
            "داده قبلی کامل نیست."
        )

    # سکه و طلا
    if (
        coin_pct is not None
        and gold_pct is not None
    ):
        if coin_pct > gold_pct + 0.20:
            coin_gold_text = (
                "سکه امامی نسبت به طلای ۱۸ عیار "
                "حرکت قوی‌تری داشته است."
            )

        elif coin_pct < gold_pct - 0.20:
            coin_gold_text = (
                "حرکت سکه امامی از طلای ۱۸ عیار "
                "ضعیف‌تر بوده است."
            )

        else:
            coin_gold_text = (
                "حرکت سکه و طلای ۱۸ عیار "
                "تقریباً هم‌جهت بوده است."
            )

    else:
        coin_gold_text = (
            "برای مقایسه سکه و طلا "
            "داده قبلی کامل نیست."
        )

    # نکته خریدار
    if (
        gold_pct is not None
        and gold_pct > 0.50
    ):
        buyer_note = (
            "با توجه به رشد اخیر قیمت، "
            "بهتر است قبل از خرید، "
            "چند نرخ متوالی مقایسه شود."
        )

    elif (
        gold_pct is not None
        and gold_pct < -0.50
    ):
        buyer_note = (
            "با توجه به کاهش اخیر، "
            "مقایسه چند نرخ متوالی "
            "قبل از خرید اهمیت دارد."
        )

    else:
        buyer_note = (
            "در بازار نوسانی، "
            "مقایسه چند نرخ متوالی و "
            "توجه به اجرت و وزن محصول اهمیت دارد."
        )

    return {
        "gold_pct": gold_pct,
        "coin_pct": coin_pct,
        "half_pct": half_pct,
        "quarter_pct": quarter_pct,
        "dollar_pct": dollar_pct,
        "gold_trend": trend_label(
            gold_pct
        ),
        "coin_trend": trend_label(
            coin_pct
        ),
        "half_trend": trend_label(
            half_pct
        ),
        "quarter_trend": trend_label(
            quarter_pct
        ),
        "dollar_trend": trend_label(
            dollar_pct
        ),
        "market_direction": market_direction,
        "strongest_text": strongest_text,
        "gold_dollar_text": gold_dollar_text,
        "coin_gold_text": coin_gold_text,
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
            "🎉 مناسبت ویژه‌ای "
            "در داده تقویم پیدا نشد."
        )

    gold_price = format_price(
        prices.get("gold18")
    )

    coin_price = format_price(
        prices.get("coin")
    )

    half_price = format_price(
        prices.get("half")
    )

    quarter_price = format_price(
        prices.get("quarter")
    )

    dollar_price = format_price(
        prices.get("dollar")
    )

    gold_change = change_text(
        analysis["gold_pct"]
    )

    coin_change = change_text(
        analysis["coin_pct"]
    )

    half_change = change_text(
        analysis["half_pct"]
    )

    quarter_change = change_text(
        analysis["quarter_pct"]
    )

    dollar_change = change_text(
        analysis["dollar_pct"]
    )

    return f"""🌙✨ زرین ماه | تحلیل روزانه بازار

📅 {today["weekday"]} | {today["date_text"]}

{occasion_text}

━━━━━━━━━━━━━━━━━━

💰 وضعیت قیمت‌های امروز

🟡 طلای ۱۸ عیار
💵 {gold_price} تومان
📊 تغییر: {gold_change}
📈 روند: {analysis["gold_trend"]}

🪙 سکه امامی
💵 {coin_price} تومان
📊 تغییر: {coin_change}
📈 روند: {analysis["coin_trend"]}

🪙 نیم‌سکه
💵 {half_price} تومان
📊 تغییر: {half_change}
📈 روند: {analysis["half_trend"]}

🪙 ربع‌سکه
💵 {quarter_price} تومان
📊 تغییر: {quarter_change}
📈 روند: {analysis["quarter_trend"]}

💵 دلار
💵 {dollar_price} تومان
📊 تغییر: {dollar_change}
📈 روند: {analysis["dollar_trend"]}

━━━━━━━━━━━━━━━━━━

📊 نبض بازار

{analysis["market_direction"]}

{analysis["strongest_text"]}

{analysis["gold_dollar_text"]}

{analysis["coin_gold_text"]}

━━━━━━━━━━━━━━━━━━

🛍 نکته برای خریداران

{analysis["buyer_note"]}

━━━━━━━━━━━━━━━━━━

📌 مبنای تحلیل

تغییرات بر اساس مقایسه قیمت فعلی
با آخرین قیمت ذخیره‌شده قبلی ربات محاسبه شده است.

━━━━━━━━━━━━━━━━━━

🌙 زرین ماه
«ویترین طلای کم‌اجرت»

📲 @ZarinMahGold
"""


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
        "Daily analysis sent successfully to Telegram."
    )

    return True


# =========================================================
# ارسال ایتا
# =========================================================

def send_to_eitaa(message):
    print(
        "Preparing Eitaa daily send..."
    )

    if not EITAAYAR_TOKEN:
        print(
            "Eitaa error: EITAAYAR_TOKEN is missing."
        )
        return False

    if not EITAA_CHAT_ID:
        print(
            "Eitaa error: EITAA_CHAT_ID is missing."
        )
        return False

    url = (
        EITAA_API_URL
        f"{EITAAYAR_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": EITAA_CHAT_ID,
        "text": message,
    }

    last_error = None

    for attempt in range(1, 3):

        try:
            print(
                f"Eitaa attempt {attempt}/2..."
            )

            response = requests.post(
                url,
                data=payload,
                timeout=30,
            )

            print(
                "Eitaa HTTP status:",
                response.status_code,
            )

            print(
                "Eitaa response:",
                response.text,
            )

            if response.status_code != 200:
                last_error = (
                    f"HTTP {response.status_code}: "
                    f"{response.text}"
                )

                if attempt < 2:
                    time.sleep(2)

                continue

            try:
                data = response.json()
            except ValueError:
                data = None

            if not isinstance(data, dict):
                last_error = (
                    "Eitaa returned a non-JSON response."
                )

                if attempt < 2:
                    time.sleep(2)

                continue

            if data.get("ok") is True:
                print(
                    "Daily analysis sent successfully to Eitaa."
                )
                return True

            last_error = (
                f"Eitaa API returned an error: {data}"
            )

            if attempt < 2:
                time.sleep(2)

        except requests.RequestException as error:
            last_error = (
                f"Eitaa request error: {repr(error)}"
            )

            print(
                "Eitaa request error:",
                repr(error),
            )

            if attempt < 2:
                time.sleep(2)

        except Exception as error:
            last_error = (
                f"Eitaa unexpected error: {repr(error)}"
            )

            print(
                "Eitaa unexpected error:",
                repr(error),
            )

            if attempt < 2:
                time.sleep(2)

    print(
        "Eitaa final error:",
        last_error,
    )

    return False


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

    eitaa_sent = daily_status[
        "eitaa"
    ]

    # اگر هر دو مقصد قبلاً ارسال شده‌اند
    if (
        scheduled_run
        or watchdog_retry
    ):
        if (
            telegram_sent
            and eitaa_sent
        ):
            print(
                "Daily analysis already sent "
                "to both destinations for:",
                current_slot,
            )
            return

    # ساخت پیام
    message = build_message()

    print(
        "Generated daily analysis:"
    )

    print(
        message
    )

    # =====================================================
    # تلگرام
    # =====================================================

    if not telegram_sent:
        print(
            "Sending daily analysis to Telegram..."
        )

        try:
            telegram_ok = send_to_telegram(
                message
            )

            if telegram_ok:
                save_daily_destination_status(
                    current_slot,
                    "telegram",
                )
                telegram_sent = True

        except Exception as error:
            print(
                "Telegram send failed:",
                repr(error),
            )

    else:
        print(
            "Telegram already sent for:",
            current_slot,
        )

    # =====================================================
    # ایتا
    # =====================================================

    if not eitaa_sent:
        print(
            "Sending daily analysis to Eitaa..."
        )

        eitaa_ok = send_to_eitaa(
            message
        )

        if eitaa_ok:
            save_daily_destination_status(
                current_slot,
                "eitaa",
            )
            eitaa_sent = True

        else:
            print(
                "Eitaa daily send failed."
            )

            print(
                "Telegram remains marked as sent."
            )

            print(
                "Eitaa will remain pending "
                "and can be retried on the next run."
            )

    else:
        print(
            "Eitaa already sent for:",
            current_slot,
        )

    # =====================================================
    # نتیجه نهایی
    # =====================================================

    if (
        telegram_sent
        and eitaa_sent
    ):
        print(
            "Daily analysis completed successfully "
            "for Telegram and Eitaa."
        )

    elif telegram_sent:
        print(
            "Daily analysis completed for Telegram. "
            "Eitaa is still pending."
        )

    elif eitaa_sent:
        print(
            "Daily analysis completed for Eitaa. "
            "Telegram is still pending."
        )

    else:
        print(
            "Daily analysis was not successfully "
            "sent to any destination."
        )


if __name__ == "__main__":
    main()
