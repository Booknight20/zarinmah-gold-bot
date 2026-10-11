# -*- coding: utf-8 -*-

import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


TEHRAN = ZoneInfo("Asia/Tehran")
BASE_URL = "https://t.me/s/rahavard365"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 20
MAX_PAGES = 6

PERSIAN_MONTHS = (
    "فروردین", "اردیبهشت", "خرداد", "تیر",
    "مرداد", "شهریور", "مهر", "آبان",
    "آذر", "دی", "بهمن", "اسفند",
)


def _normalize_digits(value):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٬٫",
        "01234567890123456789,.",
    )
    return str(value).translate(table)


def _plain_text(raw):
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(
        r"</(?:div|p|article|section|h[1-6])\s*>",
        "\n",
        raw,
        flags=re.I,
    )
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = raw.replace("\xa0", " ")
    raw = raw.replace("‌", " ")
    return re.sub(r"\n\s*\n+", "\n", raw).strip()


def _fetch_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    posts = re.findall(
        r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
        response.text,
        flags=re.I | re.S,
    )

    messages = [_plain_text(post) for post in posts]

    ids = [
        int(value)
        for value in re.findall(
            r'data-post="rahavard365/(\d+)"',
            response.text,
            flags=re.I,
        )
    ]

    return messages, ids


def _get_posts(max_pages=MAX_PAGES):
    """خواندن چند صفحه اخیر کانال عمومی ره‌آورد."""
    collected = []
    url = BASE_URL
    visited_oldest_ids = set()

    for _ in range(max_pages):
        try:
            messages, ids = _fetch_page(url)
        except Exception as exc:
            print("Rahavard page error:", repr(exc))
            break

        collected.extend(messages)

        if not ids:
            break

        oldest_id = min(ids)

        if oldest_id in visited_oldest_ids:
            break

        visited_oldest_ids.add(oldest_id)
        url = BASE_URL + "?before=" + str(oldest_id)

    # حذف متن‌های تکراری، با حفظ ترتیب
    result = []
    seen = set()

    for post in collected:
        key = post.strip()

        if key and key not in seen:
            seen.add(key)
            result.append(key)

    return result


def _parse_amount(text):
    """تبدیل مبلغ به میلیارد تومان."""
    value = _normalize_digits(text).replace(",", "")

    pattern = (
        r"(?<!\d)([+-]?)\s*(\d+(?:\.\d+)?)"
        r"\s*([+-]?)\s*(همت|میلیارد|میلیون)?"
    )

    match = re.search(pattern, value)

    if not match:
        return None

    sign = match.group(1) or match.group(3)
    number = float(match.group(2))
    unit = match.group(4) or "میلیارد"

    if sign == "-":
        number = -number

    if unit == "همت":
        number *= 1000
    elif unit == "میلیون":
        number /= 1000

    return number


def _format_billion(value):
    if value is None:
        return "نامشخص"

    sign = "+" if value > 0 else ("−" if value < 0 else "")
    number = abs(value)

    if number >= 1000:
        return f"{sign}{number / 1000:.2f} همت"

    return f"{sign}{number:.1f} میلیارد تومان"


def _extract_date_key(text):
    """استخراج تاریخ شمسی از متن گزارش."""
    normalized = _normalize_digits(text)

    months = "|".join(PERSIAN_MONTHS)

    match = re.search(
        r"(\d{1,2})\s+(" + months + r")\s+(\d{4})",
        normalized,
    )

    if not match:
        return None

    day = int(match.group(1))
    month = match.group(2)
    year = int(match.group(3))

    return year, month, day


def _latest_rahavard_report(posts=None):
    if posts is None:
        posts = _get_posts()

    for report in reversed(posts):
        normalized = report.replace("‌", " ")

        has_title = (
            "گزارش روزانه" in normalized
            or "وضعیت ورود و خروج پول" in normalized
        )

        has_category = any(
            word in normalized
            for word in (
                "معاملات خرد",
                "درآمد ثابت",
                "صندوق اهرمی",
            )
        )

        if has_title and has_category:
            return report

    raise ValueError("گزارش روزانه ره‌آورد پیدا نشد.")


def _latest_gold_funds_report(posts=None):
    """جست‌وجوی گزارش اختصاصی جریان پول صندوق‌های طلا."""
    if posts is None:
        posts = _get_posts()

    for report in reversed(posts):
        text = report.replace("‌", " ")

        title_match = (
            "گزارش ورود پول حقیقی به صندوق‌های طلا" in text
            or "گزارش ورود پول حقیقی به صندوق های طلا" in text
            or "گزارش خروج پول حقیقی از صندوق‌های طلا" in text
            or "گزارش خروج پول حقیقی از صندوق های طلا" in text
        )

        has_gold = "صندوق" in text and "طلا" in text
        has_flow = (
            "پول حقیقی" in text
            and (
                "وارد شد" in text
                or "خارج شد" in text
                or "ورود پول" in text
                or "خروج پول" in text
            )
        )

        if title_match or (has_gold and has_flow):
            return report

    return None


def _parse_gold_fund_flow(report):
    """
    استخراج جریان پول صندوق‌های طلا.
    خروجی بر حسب میلیارد تومان است.
    اگر مبلغ یا جهت روشن نباشد، None برمی‌گرداند.
    """
    if not report:
        return None

    text = _normalize_digits(report).replace(",", "")

    # مبلغ باید به واحد مالی مشخصی متصل باشد.
    amount_match = re.search(
        r"(\d+(?:\.\d+)?)"
        r"[^0-9\n]{0,40}"
        r"(همت|میلیارد|میلیون)",
        text,
    )

    if not amount_match:
        return None

    amount = float(amount_match.group(1))
    unit = amount_match.group(2)

    if unit == "همت":
        amount *= 1000
    elif unit == "میلیون":
        amount /= 1000

    # خروج را پیش از ورود بررسی می‌کنیم.
    if re.search(
        r"خروج پول|پول حقیقی.*?خارج شد|پول.*?از صندوق.*?خارج",
        text,
    ):
        return -amount

    if re.search(
        r"ورود پول|پول حقیقی.*?وارد شد|پول.*?به صندوق.*?وارد",
        text,
    ):
        return amount

    return None


def _flow_status(value):
    if value is None:
        return "داده نامشخص"
    if value > 0:
        return "ورود پول"
    if value < 0:
        return "خروج پول"
    return "تقریباً خنثی"


def build_capital_flow_section(prices=None, previous=None):
    now = datetime.now(TEHRAN).strftime("%H:%M")

    parts = [
        "💧 گزارش جریان نقدینگی بازار",
        "🕒 زمان بررسی: " + now + " به وقت تهران",
        "منبع: کانال عمومی ره‌آورد ۳۶۵",
    ]

    try:
        posts = _get_posts()
    except Exception as exc:
        posts = []
        print("Rahavard source error:", repr(exc))

    market_report = None

    try:
        market_report = _latest_rahavard_report(posts)

        parts.extend([
            "",
            "📊 گزارش روزانه بازار:",
            market_report,
            "",
            "🧭 جریان پول حقیقی بازار:",
        ])

        categories = {
            "معاملات خرد سهام": [r"معاملات\s*خرد"],
            "صندوق‌های درآمد ثابت": [r"درآمد\s*ثابت"],
            "صندوق‌های اهرمی": [
                r"صندوق\s*های?\s*اهرم",
                r"صندوق\s*اهرم",
            ],
        }

        for label, patterns in categories.items():
            amount = None

            for line in market_report.splitlines():
                if any(
                    re.search(pattern, line.replace("‌", " "))
                    for pattern in patterns
                ):
                    amount = _parse_amount(line)

                    if amount is not None:
                        break

            if amount is None:
                parts.append(
                    "• " + label + ": رقم قابل استخراج نیست."
                )
            else:
                parts.append(
                    "• " + label + ": "
                    + _format_billion(amount)
                    + " — " + _flow_status(amount)
                )

    except Exception as exc:
        parts.extend([
            "",
            "⚠️ گزارش روزانه بازار دریافت نشد.",
        ])
        print("Market report error:", repr(exc))

    parts.extend([
        "",
        "🪙 جریان پول صندوق‌های طلای بورسی:",
    ])

    try:
        gold_report = _latest_gold_funds_report(posts)

        if not gold_report:
            parts.append(
                "⚠️ گزارش اختصاصی جریان پول صندوق‌های طلا "
                "در صفحات بررسی‌شده پیدا نشد."
            )
        else:
            market_date = (
                _extract_date_key(market_report)
                if market_report
                else None
            )
            gold_date = _extract_date_key(gold_report)

            if gold_date:
                day, month, year = (
                    gold_date[2],
                    gold_date[1],
                    gold_date[0],
                )
                date_text = f"{day} {month} {year}"
            else:
                date_text = "تاریخ نامشخص"

            if not market_date or not gold_date:
                parts.append(
                    "⚠️ تاریخ گزارش صندوق‌های طلا با اطمینان "
                    "قابل مقایسه نیست."
                )
                parts.append("تاریخ گزارش پیدا‌شده: " + date_text)
                parts.append(
                    "برای جلوگیری از انتشار آمار قدیمی، "
                    "مبلغ آن به‌عنوان آمار امروز نمایش داده نشد."
                )

            elif gold_date != market_date:
                parts.append(
                    "⚠️ آخرین گزارش پیدا‌شده مربوط به تاریخ دیگری است."
                )
                parts.append("تاریخ گزارش: " + date_text)
                parts.append(
                    "مبلغ گزارش قدیمی به‌عنوان جریان پول امروز "
                    "محاسبه یا منتشر نمی‌شود."
                )

            else:
                gold_flow = _parse_gold_fund_flow(gold_report)

                parts.append("🗓 تاریخ گزارش: " + date_text)

                if gold_flow is None:
                    parts.append(
                        "⚠️ گزارش امروز پیدا شد، اما مبلغ یا جهت "
                        "جریان پول به‌طور مطمئن استخراج نشد."
                    )
                else:
                    parts.append(
                        "💰 خالص جریان پول حقیقی: "
                        + _format_billion(gold_flow)
                    )
                    parts.append(
                        "📍 وضعیت: " + _flow_status(gold_flow)
                    )

                parts.extend([
                    "",
                    "📄 متن گزارش صندوق‌های طلا:",
                    gold_report,
                ])

    except Exception as exc:
        parts.append(
            "⚠️ بررسی گزارش صندوق‌های طلا موفق نبود."
        )
        print("Gold funds error:", repr(exc))

    parts.extend([
        "",
        "🏭 صنایع بورسی",
        "رتبه‌بندی صنایع هنوز استخراج نمی‌شود.",
        "",
        "📈 طلا و دلار",
        "تغییر قیمت به‌تنهایی اثبات‌کننده ورود یا خروج پول نیست.",
        "",
        "🧠 جمع‌بندی",
        "جریان پول صندوق‌های طلا باید در کنار قیمت طلا، "
        "دلار و حباب صندوق‌ها بررسی شود.",
        "این گزارش توصیه قطعی خریدوفروش نیست.",
    ])

    if prices and previous:
        labels = {
            "gold18": "طلای ۱۸ عیار",
            "dollar": "دلار آزاد",
        }

        trends = []

        for key, label in labels.items():
            try:
                current = float(prices.get(key))
                old = float(previous.get(key))

                if old <= 0:
                    continue

                percent = (current - old) / old * 100

                if percent > 0:
                    direction = "افزایش قیمت"
                elif percent < 0:
                    direction = "کاهش قیمت"
                else:
                    direction = "بدون تغییر"

                trends.append(
                    "• " + label + ": " + direction
                    + " (" + f"{percent:+.2f}" + "%)"
                    + "؛ این شاخص جریان پول نیست."
                )

            except (TypeError, ValueError, AttributeError):
                continue

        if trends:
            parts.extend(["", "📉 روند قیمت:", *trends])

    return "\n".join(parts)
