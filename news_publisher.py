import hashlib
import json
import os
from datetime import datetime

import requests


INPUT_FILE = "news_ready.json"
PUBLISHED_FILE = "news_published.json"

CHANNEL = "@ZarinMahGold"

MAX_NEWS_PER_RUN = 2

TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN"
)


def now_iso():
    return datetime.now().astimezone().isoformat()


def parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    except Exception:
        return None


def load_json_file(filename, default):
    if not os.path.exists(filename):
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

    result = response.json()

    if not result.get("ok"):
        print(result)

        raise RuntimeError(
            "Telegram API returned ok=false."
        )

    return result


def get_collected_datetime(item):
    return parse_datetime(
        item.get(
            "collected_at",
            "",
        )
    )


def get_sort_value(item):
    return (
        item.get("published")
        or item.get("collected_at")
        or ""
    )


def initialize_publisher(published):
    """
    اولین اجرا فقط نقطه شروع را ثبت می‌کند.
    خبرهای قدیمی منتشر نمی‌شوند.
    """

    meta = published.get(
        "__meta__"
    )

    if isinstance(meta, dict):
        initialized_at = parse_datetime(
            meta.get(
                "initialized_at"
            )
        )

        if initialized_at:
            return initialized_at, False

    initialized_at = (
        datetime.now().astimezone()
    )

    published["__meta__"] = {
        "initialized_at": (
            initialized_at.isoformat()
        )
    }

    save_json_file(
        PUBLISHED_FILE,
        published,
    )

    return initialized_at, True


def main():
    print(
        "==================================="
    )
    print(
        "ZarinMah News Publisher"
    )
    print(
        "==================================="
    )

    if not TELEGRAM_BOT_TOKEN:
        print(
            "ERROR: TELEGRAM_BOT_TOKEN is missing."
        )
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing."
        )

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

    initialized_at, is_first_run = (
        initialize_publisher(
            published
        )
    )

    if is_first_run:
        print(
            "Publisher initialized."
        )
        print(
            "No old news will be published "
            "on the first run."
        )
        return

    print(
        "Publisher initialized at:",
        initialized_at.isoformat(),
    )

    high_priority_news = [
        item
        for item in news
        if item.get(
            "priority"
        ) == "high"
    ]

    high_priority_news.sort(
        key=get_sort_value,
        reverse=True,
    )

    print(
        "Total ready news:",
        len(news),
    )

    print(
        "High priority news:",
        len(high_priority_news),
    )

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    for item in high_priority_news:

        if sent_count >= MAX_NEWS_PER_RUN:
            print(
                "Maximum news per run reached."
            )
            break

        news_id = create_news_id(
            item
        )

        if news_id in published:
            skipped_count += 1
            continue

        collected_at = (
            get_collected_datetime(
                item
            )
        )

        if collected_at is None:
            print(
                "Skipping news with invalid "
                "collection time:"
            )
            print(
                item.get(
                    "title",
                    "",
                )
            )
            skipped_count += 1
            continue

        # خبرهای قبل از فعال شدن Publisher
        # منتشر نمی‌شوند.
        if collected_at <= initialized_at:
            skipped_count += 1
            continue

        message = build_message(
            item
        )

        if not message.strip():
            skipped_count += 1
            continue

        print()
        print(
            "Publishing:",
            item.get(
                "title",
                "",
            ),
        )

        try:
            telegram_result = (
                send_to_telegram(
                    message
                )
            )

        except Exception as error:
            print(
                "Publishing failed:",
                error,
            )

            failed_count += 1

            # برای اینکه GitHub Workflow قرمز شود
            # و Watchdog بتواند Retry کند،
            # از این خبر عبور می‌کنیم ولی خطا را ثبت می‌کنیم.
            continue

        message_id = (
            telegram_result.get(
                "result",
                {},
            ).get(
                "message_id"
            )
        )

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
            "published_at": now_iso(),
            "telegram_message_id": (
                message_id
            ),
        }

        # بلافاصله بعد از موفقیت ذخیره می‌کنیم
        # تا Retry باعث ارسال دوباره نشود.
        save_json_file(
            PUBLISHED_FILE,
            published,
        )

        sent_count += 1

    print()
    print(
        "==================================="
    )
    print(
        "Publishing finished"
    )
    print(
        "==================================="
    )

    print(
        "Published this run:",
        sent_count,
    )

    print(
        "Already published/skipped:",
        skipped_count,
    )

    print(
        "Failed this run:",
        failed_count,
    )

    # اگر حتی یک ارسال ناموفق بوده،
    # Workflow باید قرمز شود.
    # این باعث می‌شود Watchdog آن را Retry کند.
    if failed_count > 0:
        raise RuntimeError(
            f"{failed_count} Telegram "
            "publication(s) failed."
        )


if __name__ == "__main__":
    main()
