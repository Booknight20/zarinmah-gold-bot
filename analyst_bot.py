import html
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


TEHRAN_TZ = ZoneInfo("Asia/Tehran")

OUTPUT_FILE = "analyst_ready.json"
SEEN_FILE = "analyst_seen.json"


ANALYSTS = {
    "پیام الیاس کردی": {
        "channel": "Payamelyaskordi",
    },
    "دکتر آرش امینی": {
        "channel": "drarashamini",
    },
    "حسین نصیری": {
        "channel": "nasiirry",
    },
    "علیرضا محرابی": {
        "channel": "AlirezaMehrabi_ir",
    },
    "ره‌آورد ۳۶۵": {
        "channel": "rahavard365",
    },
}


MARKET_KEYWORDS = [
    "طلا",
    "طلای ۱۸",
    "طلای 18",
    "طلای آبشده",
    "آبشده",
    "اونس",
    "اونس جهانی",
    "سکه",
    "سکه امامی",
    "نیم سکه",
    "ربع سکه",
    "حباب طلا",
    "حباب سکه",
    "دلار",
    "دلار آزاد",
    "ارز",
    "نرخ ارز",
    "بازار ارز",
    "یورو",
    "درهم",
    "پوند",
    "ریال",
    "مرکز مبادله",
    "دلار محاسباتی",
    "بورس",
    "بازار سرمایه",
    "شاخص",
    "شاخص کل",
    "شاخص کل بورس",
    "شاخص هم وزن",
    "شاخص هم‌وزن",
    "فرابورس",
    "نماد",
    "ارزش معاملات",
    "ارزش بازار",
    "عرضه اولیه",
    "ورود پول حقیقی",
    "خروج پول حقیقی",
    "پول حقیقی",
    "پول هوشمند",
    "جریان نقدینگی",
    "نقدینگی",
    "صندوق طلا",
    "صندوق‌های طلا",
    "صندوق نقره",
    "صندوق‌های نقره",
    "گواهی سپرده",
    "گواهی سپرده شمش",
    "نرخ بهره",
    "فدرال رزرو",
    "تورم",
    "بانک مرکزی",
    "سیاست پولی",
    "سیاست ارزی",
    "پایه پولی",
    "کسری بودجه",
    "رشد اقتصادی",
    "رکود",
    "قیمت نفت",
    "نفت",
    "تحریم",
    "اوراق",
    "بازده اوراق",
    "بازدهی",
    "ارزش ذاتی",
    "حباب صندوق",
]


PROMOTIONAL_KEYWORDS = [
    "ثبت نام",
    "ثبت‌نام",
    "دوره",
    "وبینار",
    "پکیج",
    "مشاوره",
    "فروش ویژه",
    "کد تخفیف",
    "پلتفرم",
    "عضویت ویژه",
    "vip",
    "خرید",
    "اشتراک",
    "اشتراک ویژه",
]


def now_iso():
    return datetime.now(
        TEHRAN_TZ
    ).isoformat()


def clean_html(text):
    if not text:
        return ""

    text = re.sub(
        r"<br\s*/?>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"</p>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = html.unescape(text)

    text = text.replace(
        "\u200c",
        " ",
    )

    text = text.replace(
        "\u200f",
        " ",
    )

    text = re.sub(
        r"\n\s*\n+",
        "\n",
        text,
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    return text.strip()


def normalize(text):
    text = text or ""

    text = text.replace(
        "ي",
        "ی",
    )

    text = text.replace(
        "ك",
        "ک",
    )

    text = text.replace(
        "ى",
        "ی",
    )

    text = text.replace(
        "ة",
        "ه",
    )

    return text.lower()


def load_seen():
    default = {
        "sources": {}
    }

    if not os.path.exists(
        SEEN_FILE
    ):
        return default

    try:
        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(
            data,
            dict,
        ):
            return default

        data.setdefault(
            "sources",
            {}
        )

        return data

    except Exception as error:
        print(
            "Could not load seen data:",
            error,
        )

        return default


def save_seen(data):
    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def save_ready(data):
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def fetch_channel(channel):
    url = f"https://t.me/s/{channel}"

    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; ZarinMahBot/1.0)"
            )
        },
        timeout=30,
    )

    response.raise_for_status()

    page = response.text

    pattern = re.compile(
        r'<a class="tgme_widget_message_date[^"]*"'
        r'\s+href="([^"]+)"[^>]*>.*?</a>'
        r'.*?'
        r'<div class="tgme_widget_message_text[^"]*"'
        r'[^>]*>(.*?)</div>',
        re.DOTALL,
    )

    posts = []

    for match in pattern.finditer(
        page
    ):
        link = match.group(1)
        raw_text = match.group(2)

        text = clean_html(
            raw_text
        )

        if not text:
            continue

        posts.append(
            {
                "link": link,
                "text": text,
            }
        )

    return posts


def find_matches(
    text,
    keywords,
):
    normalized = normalize(
        text
    )

    matches = []

    for keyword in keywords:
        keyword_normalized = normalize(
            keyword
        )

        if keyword_normalized in normalized:
            matches.append(
                keyword
            )

    return matches


def is_relevant(text):
    market_matches = find_matches(
        text,
        MARKET_KEYWORDS,
    )

    promotional_matches = find_matches(
        text,
        PROMOTIONAL_KEYWORDS,
    )

    score = (
        len(market_matches) * 2
    )

    if len(text) > 350:
        score += 1

    if len(text) > 700:
        score += 1

    if (
        len(promotional_matches) >= 2
        and len(market_matches) < 4
    ):
        return (
            False,
            score,
            market_matches,
        )

    if score < 4:
        return (
            False,
            score,
            market_matches,
        )

    return (
        True,
        score,
        market_matches,
    )


def build_title(text):
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if lines:
        first = lines[0]

        if (
            len(first) <= 120
            and not first.startswith("@")
        ):
            return first

    sentences = re.split(
        r"(?<=[.!؟])\s+",
        text,
    )

    if sentences:
        title = sentences[0].strip()

        if len(title) > 100:
            title = (
                title[:97].rstrip()
                + "..."
            )

        return title

    return "تحلیل جدید بازار"


def build_summary(text):
    text = text.strip()

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if len(lines) > 1:
        content = " ".join(
            lines[1:]
        )
    else:
        content = text

    content = re.sub(
        r"\s+",
        " ",
        content,
    ).strip()

    sentences = re.split(
        r"(?<=[.!؟])\s+",
        content,
    )

    sentences = [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]

    selected = sentences[:2]

    summary = " ".join(
        selected
    ).strip()

    if not summary:
        summary = content

    if len(summary) > 360:
        summary = (
            summary[:357].rstrip()
            + "..."
        )

    return summary


def make_item(
    source_name,
    post,
    score,
    market_matches,
):
    title = build_title(
        post["text"]
    )

    summary = build_summary(
        post["text"]
    )

    priority = (
        "high"
        if score >= 8
        else "medium"
    )

    return {
        "analyst": source_name,
        "title": title,
        "summary": summary,
        "source": source_name,
        "link": post["link"],
        "analysis_score": score,
        "market_matches": market_matches,
        "priority": priority,
        "collected_at": now_iso(),
    }


def initialize_source(
    seen,
    source_name,
    posts,
):
    """
    اگر این منبع برای اولین بار دیده می‌شود،
    تمام پست‌های فعلی فقط ثبت می‌شوند.
    """

    sources = seen.setdefault(
        "sources",
        {},
    )

    if source_name in sources:
        return False

    post_ids = [
        post["link"]
        for post in posts
        if post.get("link")
    ]

    sources[source_name] = {
        "initialized_at": now_iso(),
        "post_ids": list(
            dict.fromkeys(
                post_ids
            )
        )[-3000:],
    }

    print()
    print(
        "Initialized source:",
        source_name,
    )

    print(
        "Existing posts registered:",
        len(
            sources[source_name][
                "post_ids"
            ]
        ),
    )

    return True


def source_has_post(
    seen,
    source_name,
    post_id,
):
    sources = seen.setdefault(
        "sources",
        {},
    )

    source_data = sources.setdefault(
        source_name,
        {
            "initialized_at": now_iso(),
            "post_ids": [],
        },
    )

    return post_id in source_data.get(
        "post_ids",
        [],
    )


def mark_source_post(
    seen,
    source_name,
    post_id,
):
    sources = seen.setdefault(
        "sources",
        {},
    )

    source_data = sources.setdefault(
        source_name,
        {
            "initialized_at": now_iso(),
            "post_ids": [],
        },
    )

    post_ids = source_data.setdefault(
        "post_ids",
        [],
    )

    if post_id not in post_ids:
        post_ids.append(
            post_id
        )

    source_data["post_ids"] = list(
        dict.fromkeys(
            post_ids
        )
    )[-3000:]


def main():
    print(
        "==================================="
    )
    print(
        "ZarinMah Analyst Collector"
    )
    print(
        "==================================="
    )

    seen = load_seen()

    ready = []

    for source_name, config in ANALYSTS.items():

        print()
        print(
            "Reading:",
            source_name,
        )

        try:
            posts = fetch_channel(
                config["channel"]
            )

        except Exception as error:
            print(
                "Channel error:",
                error,
            )
            continue

        print(
            "Posts found:",
            len(posts),
        )

        # هر منبع جداگانه initialize می‌شود.
        is_new_source = initialize_source(
            seen,
            source_name,
            posts,
        )

        if is_new_source:
            continue

        for post in posts:

            post_id = post.get(
                "link"
            )

            if not post_id:
                continue

            if source_has_post(
                seen,
                source_name,
                post_id,
            ):
                continue

            # ابتدا ثبت شود تا در اجرای بعد
            # دوباره وارد صف نشود.
            mark_source_post(
                seen,
                source_name,
                post_id,
            )

            relevant, score, market_matches = (
                is_relevant(
                    post["text"]
                )
            )

            if not relevant:
                continue

            item = make_item(
                source_name,
                post,
                score,
                market_matches,
            )

            ready.append(
                item
            )

    save_seen(
        seen
    )

    ready.sort(
        key=lambda item: item.get(
            "analysis_score",
            0,
        ),
        reverse=True,
    )

    save_ready(
        ready
    )

    print()
    print(
        "New relevant analyses:",
        len(ready),
    )

    for item in ready[:10]:
        print(
            "-",
            item["analyst"],
            "|",
            item["analysis_score"],
            "|",
            item["title"],
        )


if __name__ == "__main__":
    main()
