import hashlib
import json
import os

import requests


INPUT_FILE = "news_ready.json"
PUBLISHED_FILE = "news_published.json"

CHANNEL = "@ZarinMahGold"

MAX_NEWS_PER_RUN = 2

TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN"
)


def load_json_file(filename, default):
    if not os.path.exists(filename):
        return default

    try:
        with open(
            filename,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return data

    except Exception as error:
        print(
            f"Could not load {filename}:",
            error,
        )
        return default


def save_json_file(filename, data):
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


def create_news_id(item):
    link = str(
        item.get("link", "")
    ).strip()

    title = str(
        item.get("title", "")
    ).strip()

    base = link or title

    return hashlib.sha256(
        base.encode("utf-8")
    ).hexdigest()


def build_message(item):
    title = str(
        item.get("title", "")
    ).strip()

    summary = str(
        item.get("summary", "")
    ).strip()

    source = str(
        item.get("source", "")
    ).strip()

    link = str(
        item.get("link", "")
    ).strip()

    return (
        f"📰 {title}\n\n"
        f"{summary}\n\n"
        f"📌 منبع: {source}\n"
        f"🔗 {link}"
    )


def send_to_telegram(message):
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
        "disable_web_page_preview": False,
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

    return response.json()


def get_sort_value(item):
    return (
        item.get("published")
        or item.get("collected_at")
        or ""
    )


def main():
    print("===================================")
    print("ZarinMah News Publisher")
    print("===================================")

    if not TELEGRAM_BOT_TOKEN:
        print(
            "ERROR: TELEGRAM_BOT_TOKEN is missing."
        )
        return

    news = load_json_file(
        INPUT_FILE,
        [],
    )

    published = load_json_file(
        PUBLISHED_FILE,
        {},
    )

    if not isinstance(
        published,
        dict,
    ):
        published = {}

    high_priority_news = [
        item
        for item in news
        if item.get("priority") == "high"
    ]

    high_priority_news.sort(
        key=get_sort_value,
        reverse=True,
    )

    print(
        "High priority news:",
        len(high_priority_news),
    )

    sent_count = 0

    for item in high_priority_news:

        if sent_count >= MAX_NEWS_PER_RUN:
            print(
                "Maximum news per run reached."
            )
            break

        news_id = create_news_id(item)

        if news_id in published:
            continue

        message = build_message(item)

        if not message.strip():
            continue

        print()
        print(
            "Publishing:",
            item.get("title"),
        )

        try:
            telegram_result = send_to_telegram(
                message
            )

        except Exception as error:
            print(
                "Publishing failed:",
                error,
            )
            continue

        published[news_id] = {
            "title": item.get(
                "title",
                "",
            ),
            "source": item.get(
                "source",
                "",
            ),
            "link": item.get(
                "link",
                "",
            ),
            "published_at": item.get(
                "collected_at",
                "",
            ),
            "telegram_message_id": (
                telegram_result.get(
                    "result",
                    {}
                ).get(
                    "message_id"
                )
            ),
        }

        save_json_file(
            PUBLISHED_FILE,
            published,
        )

        sent_count += 1

    print()
    print("===================================")
    print("Publishing finished")
    print("===================================")
    print(
        "Published this run:",
        sent_count,
    )


if __name__ == "__main__":
    main()
