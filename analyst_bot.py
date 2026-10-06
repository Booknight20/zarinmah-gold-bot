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
}


MARKET_KEYWORDS = [
    "طلا",
    "طلای ۱۸",
    "طلای 18",
    "اونس",
    "آبشده",
    "سکه",
    "دلار",
    "ارز",
    "یورو",
    "درهم",
    "بورس",
    "شاخص",
    "فرابورس",
    "بازار سرمایه",
    "صندوق طلا",
    "حباب",
    "نرخ بهره",
    "فدرال رزرو",
    "تورم",
    "بانک مرکزی",
    "نقدینگی",
    "نفت",
    "تحریم",
    "اوراق",
    "بازده اوراق",
    "سیاست پولی",
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

    return text.lower()


def load_seen():
    if not os.path.exists(
        SEEN_FILE
    ):
        return {
            "initialized": False,
            "post_ids": [],
        }

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
            data = {}

        data.setdefault(
            "initialized",
            False,
        )

        data.setdefault(
            "post_ids",
            [],
        )

        return data

    except Exception:
        return {
            "initialized": False,
            "post_ids": [],
        }


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


def fetch_channel(
    channel,
):
    url = (
        f"https://t.me/s/{channel}"
    )

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

    html_text = response.text

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
        html_text
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
        if normalize(
            keyword
        ) in normalized:
            matches.append(
                keyword
            )

    return matches


def is_relevant(
    text,
):
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

    # مطالب کاملاً تبلیغاتی حذف شوند
    if (
        len(promotional_matches) >= 2
        and score < 8
    ):
        return False, score

    # حداقل یک ارتباط مشخص با بازار
    if score < 4:
        return False, score

    return True, score


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
            and not first.startswith(
                "@"
            )
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

    # حذف تیتر تکراری
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

    # خلاصه کوتاه و کنترل‌شده
    if len(summary) > 360:
        summary = (
            summary[:357].rstrip()
            + "..."
        )

    return summary


def make_item(
    analyst_name,
    post,
    score,
):
    title = build_title(
        post["text"]
    )

    summary = build_summary(
        post["text"]
    )

    return {
        "analyst": analyst_name,
        "title": title,
        "summary": summary,
        "source": analyst_name,
        "link": post["link"],
        "analysis_score": score,
        "priority": (
            "high"
            if score >= 8
            else "medium"
        ),
        "collected_at": now_iso(),
    }


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

    all_posts = []

    for analyst_name, config in ANALYSTS.items():

        print()
        print(
            "Reading:",
            analyst_name,
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

        for post in posts:
            all_posts.append(
                (
                    analyst_name,
                    post,
                )
            )

    # اولین اجرا:
    # پست‌های موجود فقط علامت‌گذاری می‌شوند
    # و چیزی منتشر نمی‌شود.
    if not seen.get(
        "initialized",
        False,
    ):

        for _, post in all_posts:
            seen["post_ids"].append(
                post["link"]
            )

        seen["initialized"] = True

        seen["post_ids"] = list(
            dict.fromkeys(
                seen["post_ids"]
            )
        )[-2000:]

        save_seen(
            seen
        )

        save_ready([])

        print()
        print(
            "Analyst collector initialized."
        )

        print(
            "Existing analyst posts "
            "will not be published."
        )

        return

    ready = []

    for analyst_name, post in all_posts:

        post_id = post["link"]

        if post_id in seen[
            "post_ids"
        ]:
            continue

        seen["post_ids"].append(
            post_id
        )

        relevant, score = is_relevant(
            post["text"]
        )

        if not relevant:
            continue

        item = make_item(
            analyst_name,
            post,
            score,
        )

        ready.append(
            item
        )

    seen["post_ids"] = list(
        dict.fromkeys(
            seen["post_ids"]
        )
    )[-2000:]

    save_seen(
        seen
    )

    # مهم‌ترین تحلیل‌ها اول
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
