# -*- coding: utf-8 -*-

import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


TEHRAN = ZoneInfo("Asia/Tehran")
URL = "https://t.me/s/rahavard365"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 20


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
    return re.sub(r"\n\s*\n+", "\n", raw).strip()


def _get_posts():
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    posts = re.findall(
        r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
        response.text,
        flags=re.I | re.S,
    )

    return [_plain_text(post) for post in posts]


def _parse_amount(text):
    """تبدیل مبلغ به میلیارد تومان؛ علامت قبل یا بعد عدد پذیرفته می‌شود."""
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


def _latest_rahavard_report():
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


def _latest_gold_funds_report():
    """جست‌وجوی آخرین پست مرتبط با جریان پول صندوق‌های طلا."""
    posts = _get_posts()

    for report in reversed(posts):
        text = report.replace("‌", " ")
        lower_text = text.lower()

        has_gold = (
            "صندوق طلا" in text
            or "صندوق‌های طلا" in text
            or "صندوق های طلا" in text
        )

        has_flow = any(
            phrase in text
            for phrase in (
                "ورود پول",
                "خروج پول",
                "پول حقیقی",
                "وارد شد",
                "خارج شد",
            )
        )

        if has_gold and has_flow:
            return report

    return None


def _parse_gold_fund_flow(report):
    """
    استخراج خالص ورود یا خروج پول صندوق‌های طلا.
    خروجی بر حسب میلیارد تومان است.
    اگر جهت جریان یا مبلغ مشخص نباشد، None برمی‌گرداند.
    """
    if not report:
        return None

    text = _normalize_digits(report).replace(",", "")

    amount_match = re.search(
        r"(\d+(?:\.\d+)?)\s*"
        r"(همت|میلیارد(?:\s*تومان(?:ی)?)?|میلیون)"
        r"(?:\s+تومان(?:ی)?)?",
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

    # ابتدا جهت جریان را از عبارت‌های صریح تشخیص می‌دهیم.
    if re.search(r"خروج\s+پول|پول.*?خارج\s+شد", text):
        return -amount

    if re.search(r"ورود\s+پول|پول.*?وارد\s+شد", text):
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

    report = ""

    try:
        report = _latest_rahavard_report()
        parts.extend([
            "",
            "📊 گزارش روزانه بازار:",
            report,
        ])
    except Exception as exc:
        parts.extend([
            "",
            "⚠️ دریافت گزارش روزانه بازار موفق نبود.",
        ])
        print("Market report error:", repr(exc))

    if report:
        parts.extend([
            "",
            "🧭 جریان پول حقیقی بازار:",
        ])

        categories = {
            "معاملات خرد سهام": [r"معاملات\s*خرد"],
            "صندوق‌های درآمد ثابت": [r"درآمد\s*ثابت"],
            "صندوق‌های اهرمی": [
                r"صندوق\s*های?\s*اهرم",
                r"صندوق‌های اهرمی",
                r"صندوق\s*اهرم",
            ],
        }

        for label, patterns in categories.items():
            amount = None

            for line in report.splitlines():
                normalized = line.replace("‌", " ")

                if any(
                    re.search(pattern, normalized)
                    for pattern in patterns
                ):
                    amount = _parse_amount(normalized)
                    if amount is not None:
                        break

            if amount is None:
                parts.append("• " + label + ": رقم قابل استخراج نیست.")
            else:
                parts.append(
                    "• " + label + ": "
                    + _format_billion(amount)
                    + " — " + _flow_status(amount)
                )

    # بخش جدید: صندوق‌های طلای بورسی
    parts.extend([
        "",
        "🪙 جریان پول صندوق‌های طلای بورسی:",
    ])

    try:
        gold_report = _latest_gold_funds_report()

        if gold_report:
            gold_flow = _parse_gold_fund_flow(gold_report)

            parts.append("📊 آخرین گزارش مرتبط ره‌آورد:")
            parts.append(gold_report)

            if gold_flow is not None:
                parts.append(
                    "💰 خالص جریان پول گزارش‌شده: "
                    + _format_billion(gold_flow)
                )
                parts.append(
                    "📍 وضعیت: " + _flow_status(gold_flow)
                )
            else:
                parts.append(
                    "⚠️ مبلغ یا جهت جریان پول از متن گزارش "
                    "به‌طور مطمئن قابل استخراج نیست."
                )
        else:
            parts.append(
                "⚠️ گزارش مشخص و قابل استخراج جریان پول "
                "صندوق‌های طلا در پست‌های بررسی‌شده پیدا نشد."
            )

    except Exception as exc:
        parts.append(
            "⚠️ دریافت اطلاعات صندوق‌های طلا موفق نبود."
        )
        print("Gold funds error:", repr(exc))

    parts.extend([
        "",
        "🏭 صنایع بورسی",
        "رتبه‌بندی صنایع در این نسخه هنوز استخراج نمی‌شود.",
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
