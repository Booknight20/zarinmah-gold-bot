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
MAX_PAGES = 20

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
    """خواندن چندین صفحه از کانال عمومی ره‌آورد."""
    collected = []
    url = BASE_URL
    visited_oldest_ids = set()

    for page_number in range(max_pages):
        try:
            messages, ids = _fetch_page(url)
        except Exception as exc:
            print(
                "Rahavard page error:",
                page_number + 1,
                repr(exc),
            )
            break

        if not messages:
            break

        collected.extend(messages)

        if not ids:
            break

        oldest_id = min(ids)

        if oldest_id in visited_oldest_ids:
            break

        visited_oldest_ids.add(oldest_id)
        url = BASE_URL + "?before=" + str(oldest_id)

    result = []
    seen = set()

    for post in collected:
        key = post.strip()

        if key and key not in seen:
            seen.add(key)
            result.append(key)

    return result


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
    """جست‌وجوی گزارش‌های مرتبط با جریان پول صندوق‌های طلا."""
    if posts is None:
        posts = _get_posts()

    # ترتیب دریافت حفظ می‌شود تا ابتدا پست‌های جدیدتر بررسی شوند.
    for report in posts:
        text = report.replace("‌", " ")

        has_gold = (
            "صندوق طلا" in text
            or "صندوق‌های طلا" in text
            or "صندوق های طلا" in text
            or "صندوق‌های طلایی" in text
        )

        has_flow = (
            "پول حقیقی" in text
            or "ورود پول" in text
            or "خروج پول" in text
            or "وارد شد" in text
            or "خارج شد" in text
        )

        if has_gold and has_flow:
            return report

    return None


def _parse_gold_fund_flow(report):
    """
    استخراج مبلغ جریان پول صندوق‌های طلا.
    نتیجه بر حسب میلیارد تومان است.
    در صورت نامشخص بودن جهت جریان، None برمی‌گرداند.
    """
    if not report:
        return None

    text = _normalize_digits(report).replace(",", "")

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

    # جهت جریان فقط با عبارت صریح تعیین می‌شود.
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
        posts = _
