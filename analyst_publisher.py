import hashlib
import html
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


TEHRAN_TZ = ZoneInfo(
    "Asia/Tehran"
)

INPUT_FILE = (
    "analyst_ready.json"
)

PUBLISHED_FILE = (
    "analyst_published.json"
)

CHANNEL = "@ZarinMahGold"

MAX_ANALYSES_PER_RUN = 1

TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN"
)


def now_iso():
    return datetime.now(
        TEHRAN_TZ
    ).isoformat()


def load_json(
    filename,
    default,
):
    if not os.path.exists(
        filename
    ):
        return default

    try:
        with open(
            filename,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except Exception as error:
        print(
            f"Could not load {filename}:",
            error,
        )
        return default


def save_json(
    filename,
    data,
):
    with open(
        filename,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def create_id(item):
    base = (
        item.get("link")
        or item.get("title")
        or ""
    )

    return hashlib.sha256(
        base.encode("utf-8")
    ).hexdigest()


def build_message(item):
    analyst = html.escape(
        str(
            item.get(
                "analyst",
                "",
            )
        )
    )

    title = html.escape(
        str(
            item.get(
                "title",
                "",
            )
        )
    )

    summary = html.escape(
        str(
            item.get(
                "summary",
                "",
            )
        )
    )

    link = html.escape(
        str(
            item.get(
                "link",
                "",
            )
        ),
        quote=True,
    )

    return (
        "🌙 <b>زرین ماه</b>\n\n"
        "📊 <b>تحلیل بازار</b>\n\n"
        f"📰 <b>{title}</b>\n\n"
        f"{summary}\n\n"
        f"📌 <b>تحلیلگر:</b> {analyst}\n"
        f'<a href="{link}">🔗 مشاهده تحلیل کامل</a>\n\n'
        "🌙 <b>برای دنبال‌کردن اخبار و تحلیل‌های بیشتر زرین ماه:</b>\n\n"
        '<a href="https://t.me/Zarimahgold">🔗 عضویت در کانال تلگرام زرین ماه</a>'
    )


def send_to_telegram(
    message
):
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing."
        )

    url = (
        "https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": CHANNEL,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30,
    )

    print(
        "Telegram response:",
        response.status_code,
    )

    if response.status_code != 200:
        print(response.text)

        raise RuntimeError(
            "Telegram message failed."
        )

    result = response.json()

    if not result.get("ok"):
        print(result)

        raise RuntimeError(
            "Telegram API returned ok=false."
        )

    return result


def main():
    print(
        "==================================="
    )
    print(
        "ZarinMah Analyst Publisher"
    )
    print(
        "==================================="
    )

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing."
        )

    analyses = load_json(
        INPUT_FILE,
        [],
    )

    published = load_json(
        PUBLISHED_FILE,
        {},
    )

    if not isinstance(
        published,
        dict,
    ):
        published = {}

    if "__meta__" not in published:
        published["__meta__"] = {
            "initialized_at": now_iso()
        }

        save_json(
            PUBLISHED_FILE,
            published,
        )

        print(
            "Analyst publisher initialized."
        )

        print(
            "No old analyses will be published."
        )

        return

    high_priority = [
        item
        for item in analyses
        if item.get(
            "priority"
        ) == "high"
    ]

    high_priority.sort(
        key=lambda item: item.get(
            "analysis_score",
            0,
        ),
        reverse=True,
    )

    sent = 0
    failed = 0

    for item in high_priority:

        if sent >= MAX_ANALYSES_PER_RUN:
            break

        analysis_id = create_id(
            item
        )

        if analysis_id in published:
            continue

        message = build_message(
            item
        )

        try:
            result = send_to_telegram(
                message
            )

        except Exception as error:
            print(
                "Publishing failed:",
                error,
            )
            failed += 1
            continue

        published[analysis_id] = {
            "analyst": item.get(
                "analyst",
                "",
            ),
            "title": item.get(
                "title",
                "",
            ),
            "link": item.get(
                "link",
                "",
            ),
            "published_at": now_iso(),
            "telegram_message_id": (
                result.get(
                    "result",
                    {},
                ).get(
                    "message_id"
                )
            ),
        }

        save_json(
            PUBLISHED_FILE,
            published,
        )

        sent += 1

        print(
            "Published analysis:",
            item.get(
                "title",
                "",
            ),
        )

    print()
    print(
        "Published analyses:",
        sent,
    )

    print(
        "Failed analyses:",
        failed,
    )

    if failed:
        raise RuntimeError(
            "One or more analyst "
            "publications failed."
        )


if __name__ == "__main__":
    main()
