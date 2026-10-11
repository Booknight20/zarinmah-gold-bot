# -*- coding: utf-8 -*-
"""گزارش جریان نقدینگی برای ربات زرین ماه."""

import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

TEHRAN = ZoneInfo("Asia/Tehran")
RAHAVARD_PUBLIC_URL = "https://t.me/s/rahavard365"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ZarinMahMarketBot/1.0)"
}
TIMEOUT = 20


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
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n\s*\n+", "\n", raw)
    return raw.strip()


def _normalize_digits(value):
    translation = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٬٫",
        "01234567890123456789,.",
    )
    return str(value).translate(translation)


def _parse_amount(text):
    value = _normalize_digits(text).replace(",", "").replace(" ", "")
    match = re.search(
        r"([+-]?)\s*(\d+(?:\.\d+)?)\s*(میلیارد|همت|میلیون)?",
        value,
    )

    if not match:
        return None

    sign = -1 if match.group(1) == "-" else 1
    number = float(match.group(2))
    unit = match.group(3) or "میلیارد"

    if unit == "همت":
        number *= 1000
    elif unit == "میلیون":
        number /= 1000

    return sign * number


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

        if not any(
            re.search(pattern, normalized, re.I)
            for pattern in patterns
        ):
            continue

        amount = _parse_amount(normalized)

        if amount is None:
            continue

        if re.search(r"خروج|منفی|−", normalized) and amount > 0:
            amount = -amount

        if (
            re.search(r"ورود|مثبت|\+", normalized)
            and re.search(r"خروج", normalized)
        ):
            continue

        return amount, line.strip()

    return None, None


def _latest_rahavard_report():
    response = requests.get(
        RAHAVARD_PUBLIC_URL,
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    posts = re.findall(
        r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
        response.text,
        flags=re.I | re.S,
    )

    texts = [_plain_text(post) for post in posts]

    for text in reversed(texts):
        normalized = text.replace("‌", " ")

        has_title = (
            "گزارش روزانه" in normalized
            or "وضعیت ورود و خروج پول" in normalized
        )
        has_category = any(
            term in normalized
            for term in (
                "درآمد ثابت",
                "معاملات خرد",
                "صندوق اهرمی",
            )
        )

        if has_title and has_category:
            return text

    raise ValueError(
        "گزارش روزانه قابل تشخیص در صفحه عمومی ره‌آورد پیدا نشد."
    )


def _flow_status(value):
    if value is None:
        return "داده قابل تأیید در دسترس نیست"
    if value > 0:
        return "ورود پول حقیقی"
    if value < 0:
        return "خروج پول حقیقی"
    return "تقریباً خنثی"


def build_capital_flow_section(prices=None, previous=None):
    now = datetime.now(TEHRAN).strftime("%H:%M")

    parts = [
        "💧 گزارش جریان نقدینگی بازار",
        f"🕒 زمان بررسی: {now} به وقت تهران",
        "منبع بررسی: صفحه عمومی ره‌آورد ۳۶۵",
    ]

    report = None

    try:
        report = _latest_rahavard_report()
    except Exception as exc:
        parts.extend([
            "⚠️ دریافت گزارش جریان پول موفق نبود.",
            "ممکن است دسترسی شبکه محدود باشد یا ساختار صفحه تغییر کرده باشد.",
        ])
        print("Capital-flow source unavailable:", repr(exc))

    if report:
        parts.extend([
            "",
            "📊 آخرین گزارش عمومی قابل تشخیص:",
            report,
            "",
            "🧭 برداشت ماشینی از دسته‌بندی‌ها:",
        ])

        categories = {
            "معاملات خرد سهام": [r"معاملات\s*خرد"],
            "صندوق‌های درآمد ثابت": [r"درآمد\s*ثابت"],
            "صندوق‌های اهرمی": [
                r"صندوق\s*های?\s*اهرم",
                r"صندوق‌های اهرمی",
            ],
        }

        for label, patterns in categories.items():
            amount, raw_line = _extract_flow_line(report, patterns)

            if amount is None:
                parts.append(
                    f"• {label}: رقم ورود یا خروج پول با اطمینان استخراج نشد."
                )
            else:
                parts.append(
                    f"• {label}: {_format_billion(amount)} — "
                    f"{_flow_status(amount)}"
                )
    else:
        parts.extend([
            "",
            "📊 رقم مستقیم امروز برای معاملات خرد، صندوق‌های درآمد ثابت "
            "و صندوق‌های اهرمی قابل تأیید نیست.",
        ])

    parts.extend([
        "",
        "🏭 صنایع بورسی",
        "رتبه‌بندی صنایع بر اساس ورود و خروج پول در این نسخه ارائه نمی‌شود؛ "
        "برای آن به داده کامل معاملات و نگاشت معتبر نمادها به صنایع نیاز است.",
        "",
        "🪙 طلا و 💵 دلار",
        "از تغییر قیمت به‌تنهایی نمی‌توان ورود یا خروج پول را اثبات کرد.",
    ])

    if prices and previous:
        trend_lines = []
        labels = {
            "gold18": "طلای ۱۸ عیار",
            "dollar": "دلار آزاد",
        }

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
                    direction = "بدون تغییر محسوس قیمت"

                trend_lines.append(
                    f"• {label}: {direction} نسبت به نرخ قبلی "
                    f"({percent:+.2f}٪)؛ این شاخص جریان پول نیست."
                )
            except (TypeError, ValueError, AttributeError):
                continue

        if trend_lines:
            parts.extend([
                "",
                "📈 روند قیمت، نه جریان پول:",
                *trend_lines,
            ])

    parts.extend([
        "",
        "🧠 جمع‌بندی",
        "این گزارش ابزار پایش بازار است، نه توصیه قطعی خریدوفروش. "
        "برای ارزیابی بهتر، جریان پول معتبر، روند قیمت و ارزش معاملات "
        "باید در کنار هم بررسی شوند.",
    ])

    return "\n".join(parts)
