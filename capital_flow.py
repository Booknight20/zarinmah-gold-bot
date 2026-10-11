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
MAX_PAGES = 100

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
    raw = raw.replace("\u200c", " ")
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
    """دریافت پست‌های عمومی کانال ره‌آورد، از جدید به قدیم."""
    collected = []
    url = BASE_URL
    visited_ids = set()

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

        if oldest_id in visited_ids:
            break

        visited_ids.add(oldest_id)
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
        r"(?<![\d.])([+-]?)\s*"
        r"(\d+(?:\.\d+)?)"
        r"\s*([+-]?)\s*"
        r"(همت|میلیارد|میلیون)?"
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
    """پیدا کردن جدیدترین گزارش روزانه جریان پول."""
    if posts is None:
        posts = _get_posts()

    for report in posts:
        text = report.replace("\u200c", " ")

        has_title = (
            "گزارش روزانه" in text
            or "وضعیت ورود و خروج پول" in text
        )

        has_category = any(
            word in text
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
    """جست‌وجوی پست‌های مرتبط با جریان پول صندوق‌های طلا."""
    if posts is None:
        posts = _get_posts()

    gold_terms = (
        "صندوق طلا",
        "صندوق‌های طلا",
        "صندوق های طلا",
        "صندوق‌های طلایی",
        "صندوق طلایی",
        "صندوق‌های مبتنی بر طلا",
        "صندوق های مبتنی بر طلا",
    )

    flow_terms = (
        "پول حقیقی",
        "ورود پول",
        "خروج پول",
        "وارد شد",
        "خارج شد",
        "ورود نقدینگی",
        "خروج نقدینگی",
    )

    for report in reversed(posts):
        text = report.replace("\u200c", " ")

        has_gold = any(term in text for term in gold_terms)
        has_flow = any(term in text for term in flow_terms)

        if has_gold and has_flow:
            return report

    return None


def _parse_gold_fund_flow(report):
    """
    استخراج مبلغ جریان پول صندوق‌های طلا بر حسب میلیارد تومان.
    اگر مبلغ یا جهت جریان مشخص نباشد، None برمی‌گرداند.
    """
    if not report:
        return None

    text = _normalize_digits(report).replace(",", "")

    amount_match = re.search(
        r"([+-]?)\s*(\d+(?:\.\d+)?)\s*([+-]?)\s*"
        r"(همت|میلیارد|میلیون)",
        text,
    )

    if not amount_match:
        return None

    sign = amount_match.group(1) or amount_match.group(3)
    amount = float(amount_match.group(2))
    unit = amount_match.group(4)

    if unit == "همت":
        amount *= 1000
    elif unit == "میلیون":
        amount /= 1000

    # علامت صریح مبلغ اولویت دارد.
    if sign == "-":
        return -amount

    if sign == "+":
        return amount

    # در غیر این صورت جهت باید از عبارت گزارش مشخص شود.
    if re.search(
        r"خروج پول|خروج نقدینگی|پول حقیقی.{0,30}خارج شد",
        text,
    ):
        return -amount

    if re.search(
        r"ورود پول|ورود نقدینگی|پول حقیقی.{0,30}وارد شد",
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


def _extract_category_amount(report, category):
    """استخراج مبلغ از خط مربوط به یک گروه بازار."""
    for line in report.splitlines():
        if category in line:
            return _parse_amount(line)

    return None


def build_capital_flow_section(prices=None, previous=None):
    """ساخت متن گزارش جریان نقدینگی؛ بدون ارسال پیام تلگرام."""
    now = datetime.now(TEHRAN).strftime("%H:%M")

    parts = [
        "💧 گزارش جریان نقدینگی بازار",
        "🕒 زمان بررسی: " + now + " به وقت تهران",
        "📡 منبع: کانال عمومی ره‌آورد ۳۶۵",
    ]

    try:
        posts = _get_posts()
        report = _latest_rahavard_report(posts)

        report_date = _extract_date_key(report)
        if report_date:
            day, month, year = (
                report_date[2],
                report_date[1],
                report_date[0],
            )
            parts.append(
                f"🗓 تاریخ گزارش: {day} {month} {year}"
            )

        categories = (
            ("معاملات خرد", "🟪 معاملات خرد"),
            ("درآمد ثابت", "🟦 درآمد ثابت"),
            ("صندوق اهرمی", "🟧 صندوق‌های اهرمی"),
        )

        parts.append("")
        parts.append("📊 ورود و خروج پول حقیقی:")

        for category, label in categories:
            amount = _extract_category_amount(report, category)
            status = _flow_status(amount)

            parts.append(
                f"{label}: {_format_billion(amount)}"
                f" | {status}"
            )

        gold_report = _latest_gold_funds_report(posts)

        parts.append("")
        parts.append("🟨 صندوق‌های طلای بورسی:")

        if gold_report:
            gold_flow = _parse_gold_fund_flow(gold_report)

            if gold_flow is None:
                parts.append(
                    "⚠️ گزارش صندوق‌های طلا پیدا شد، "
                    "اما مبلغ یا جهت جریان پول قابل تشخیص نیست."
                )
            else:
                parts.append(
                    f"جریان پول: {_format_billion(gold_flow)}"
                    f" | {_flow_status(gold_flow)}"
                )
        else:
            parts.append(
                "⚠️ گزارش اختصاصی جریان پول صندوق‌های طلا "
                "در پست‌های بررسی‌شده پیدا نشد."
            )

        parts.append("")
        parts.append(
            "ℹ️ ارقام بر اساس متن گزارش منبع هستند؛ "
            "نبود گزارش اختصاصی به معنی صفر بودن جریان پول نیست."
        )

    except Exception as exc:
        print("Capital flow error:", repr(exc))
        parts.append("")
        parts.append(
            "⚠️ دریافت یا پردازش گزارش جریان پول با خطا مواجه شد."
        )

    return "\n".join(parts)
