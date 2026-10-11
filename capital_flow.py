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
    """
    استخراج اولین مبلغ از متن و تبدیل آن به میلیارد تومان.
    علامت قبل یا بعد عدد، مانند -4825 یا ۴۸۲۵-، پشتیبانی می‌شود.
    """
    value = _normalize_digits(text)
    value = value.replace(",", "")

    match = re.search(
        r"(?<!\d)([+-]?)\s*(\d+(?:\.\d+)?)"
        r"\s*([+-]?)\s*(همت|میلیارد|میلیون)?",
        value,
    )

    if not match:
        return None

    prefix_sign = match.group(1)
    number_text = match.group(2)
    suffix_sign = match.group(3)
    unit = match.group(4) or "میلیارد"

    sign_text = prefix_sign or suffix_sign
    sign = -1 if sign_text == "-" else 1

    number = float(number_text)

    if unit == "همت":
        number *= 1000
    elif unit == "میلیون":
        number /= 1000

    return sign * number


def _format_billion(value):
    if value is None:
        return "نامشخص"

    if value > 0:
        sign = "+"
    elif value < 0:
        sign = "−"
    else:
        sign = ""

    number = abs(value)

    if number >= 1000:
        return f"{sign}{number / 1000:.2f} همت"

    return f"{sign}{number:.1f} میلیارد تومان"


def _extract_flow_line(text, patterns):
    """استخراج مبلغ از خط مربوط به یک دسته بازار."""
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

        # بررسی می‌کنیم که خود عدد علامت مثبت یا منفی داشته باشد.
        normalized_digits = _normalize_digits(normalized)
        compact = re.sub(r"\s+", "", normalized_digits)

        explicit_sign = bool(
            re.search(r"[+-]?\d+(?:\.\d+)?[+-]", compact)
            or re.search(r"[+-]\d+(?:\.\d+)?", compact)
        )

        # اگر عدد علامت نداشته باشد، فقط در صورت وجود واژه صریح
        # «خروج» یا «منفی» جهت منفی در نظر گرفته می‌شود.
        if (
            not explicit_sign
            and re.search(r"خروج|منفی", normalized)
            and amount > 0
        ):
            amount = -amount

        return amount, line.strip()

    return None, None


def _latest_rahavard_report():
    """دریافت آخرین گزارش روزانه قابل تشخیص از صفحه عمومی ره‌آورد."""
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

    for report in reversed(texts):
        normalized = report.replace("‌", " ")

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
            return report

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
    """ساخت بخش جریان نقدینگی برای گزارش روزانه زرین ماه."""
    now = datetime.now(TEHRAN).strftime("%H:%M")

    parts = [
        "💧 گزارش جریان نقدینگی بازار",
        f"🕒 زمان بررسی: {
