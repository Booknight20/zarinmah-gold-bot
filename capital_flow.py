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


def _plain_text(raw):
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"</(?:div|p|article|section|h[1-6])\s*>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = raw.replace("\xa0", " ")
    return re.sub(r"\n\s*\n+", "\n", raw).strip()


def _normalize_digits(value):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٬٫",
        "01234567890123456789,.",
    )
    return str(value).translate(table)


def _parse_amount(text):
    value = _normalize_digits(text).replace(",", "")

    pattern = (
        r"(?<!\d)([+-]?)\s*(\d+(?:\.\d+)?)"
        r"\s*([+-]?)\s*(همت|میلیارد|میلیون)?"
    )
    match = re.search(pattern, value)

    if not match:
        return None

    sign_text = match.group(1) or match.group(3)
    number = float(match.group(2))
    unit = match.group(4) or "میلیارد"

    if sign_text == "-":
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


def _extract_flow_line(text, patterns):
    for line in text.splitlines():
        normalized = line.replace("‌", " ")

        if not any(re.search(p, normalized, re.I) for p in patterns):
            continue

        amount = _parse_amount(normalized)

        if amount is None:
            continue

        return amount, line.strip()

    return None, None


def _latest_rahavard_report():
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

    for post in reversed(posts):
        report = _plain_text(post)
        normalized = report.replace("‌", " ")

        has_title = (
            "گزارش روزانه" in normalized
            or "وضعیت ورود و خروج پول" in normalized
        )
        has_category = any(
            word in normalized
            for word in ("معاملات خرد", "درآمد ثابت", "صندوق اهرمی")
        )

        if has_title and has_category:
            return report

    raise ValueError("گزارش روزانه ره‌آورد پیدا نشد.")


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
        "منبع: صفحه عمومی ره‌آورد ۳۶۵",
    ]

    try:
        report = _latest_rahavard_report()
        parts.extend(["", "📊 آخرین گزارش عمومی:", report])
    except Exception as exc:
        report = ""
        parts.extend([
            "",
            "⚠️ دریافت گزارش ره‌آورد موفق نبود.",
        ])
        print("Capital-flow source unavailable:", repr(exc))

    if report:
        parts.extend(["", "🧭 جریان پول حقیقی:"])

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
            amount, raw_line = _extract_flow_line(report, patterns)

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

    parts.extend([
        "",
        "🏭 صنایع بورسی",
        "رتبه‌بندی صنایع در این نسخه در دسترس نیست.",
        "",
        "🪙 طلا و 💵 دلار",
        "تغییر قیمت به‌تنهایی اثبات‌کننده ورود یا خروج پول نیست.",
        "",
        "🧠 جمع‌بندی",
        "این گزارش ابزار پایش بازار است، نه توصیه قطعی خریدوفروش.",
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
            parts.extend(["", "📈 روند قیمت:", *trends])

    return "\n".join(parts)
