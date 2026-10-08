import hashlib
import html
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

EITAAYAR_TOKEN = os.environ.get(
    "EITAAYAR_TOKEN"
)

EITAA_CHAT_ID = os.environ.get(
    "EITAA_CHAT_ID"
)

EITAA_API_URL = "https://eitaayar.ir/api"


def now_iso():
    return (
        datetime.now()
        .astimezone()
        .isoformat()
    )


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


def load_json_file(
    filename,
    default,
):
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


def save_json_file(
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


def create_news_id(item):
    link = str(
        item.get(
            "link",
            "",
        )
    ).strip()

    title = str(
        item.get(
            "title",
            "",
        )
    ).strip()

    base = link or title

    return hashlib.sha256(
        base.encode(
            "utf-8"
        )
    ).hexdigest()


def build_message(item):
    title = str(
        item.get(
            "title",
            "",
        )
    ).strip()

    summary = str(
        item.get(
            "summary",
            "",
        )
    ).strip()

    source = str(
        item.get(
            "source",
            "",
        )
    ).strip()

    news_link = str(
        item.get(
            "link",
            "",
        )
    ).strip()

    safe_title = html.escape(
        title
    )

    safe_summary = html.escape(
        summary
    )

    safe_source = html.escape(
        source
    )

    safe_news_link = html.escape(
        news_link,
        quote=True,
    )

    return (
        "🌙 <b>زرین ماه</b>\n\n"
        f"📰 <b>{safe_title}</b>\n\n"
        f"{safe_summary}\n\n"
        f"📌 <b>منبع:</b> {safe_source}\n"
        f'<a href="{safe_news_link}">🔗 مشاهده خبر کامل</a>\n\n'
        "🌙 <b>برای دنبال‌کردن اخبار و تحلیل‌های بیشتر زرین ماه:</b>\n\n"
        '<a href="https://t.me/Zarinmahgold">'
        "🔗 عضویت در کانال تلگرام زرین ماه"
        "</a>"
    )


def build_eitaa_message(item):
    title = str(
        item.get(
            "title",
            "",
        )
    ).strip()

    summary = str(
        item.get(
            "summary",
            "",
        )
    ).strip()

    source = str(
        item.get(
            "source",
            "",
        )
    ).strip()

    news_link = str(
        item.get(
            "link",
            "",
        )
    ).strip()

    return (
        "🌙 زرین ماه\n\n"
        f"📰 {title}\n\n"
        f"{summary}\n\n"
        f"📌 منبع: {source}\n"
        f"🔗 مشاهده خبر کامل:\n{news_link}\n\n"
        "🌙 برای دنبال‌کردن اخبار و تحلیل‌های بیشتر زرین ماه"
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
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30,
    )

    print(
        "Telegram HTTP status:",
        response.status_code,
    )

    print(
        "Telegram response:",
        response.text,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Telegram message failed."
        )

    result = response.json()

    if not result.get(
        "ok"
    ):
        raise RuntimeError(
            "Telegram API returned ok=false."
        )

    return result


def send_to_eitaa(message):
    if not EITAAYAR_TOKEN:
        raise RuntimeError(
            "EITAAYAR_TOKEN is missing."
        )

    if not EITAA_CHAT_ID:
        raise RuntimeError(
            "EITAA_CHAT_ID is missing."
        )

    token = EITAAYAR_TOKEN.strip()
    chat_id = EITAA_CHAT_ID.strip()
    chat_id = chat_id.lstrip("@")

    url = (
        f"{EITAA_API_URL}/"
        f"{token}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": message,
    }

    print(
        "Sending news message to Eitaa..."
    )

    print(
        "Eitaa HTTP status: waiting..."
    )

    response = requests.post(
        url,
        data=payload,
        timeout=30,
    )

    print(
        "Eitaa HTTP status:",
        response.status_code,
    )

    print(
        "Eitaa response:",
        response.text,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Eitaa HTTP request failed."
        )

    try:
        result = response.json()

    except ValueError:
        raise RuntimeError(
            "Eitaa API returned invalid JSON."
        )

    if not result.get(
        "ok"
    ):
        raise RuntimeError(
            f"Eitaa API returned ok=false: {result}"
        )

    print(
        "Eitaa message sent successfully."
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


def initialize_publisher(
    published
):
    meta = published.get(
        "__meta__"
    )

    if isinstance(
        meta,
        dict,
    ):
        initialized_at = parse_datetime(
            meta.get(
                "initialized_at"
            )
        )

        if initialized_at:
            return (
                initialized_at,
                False,
            )

    initialized_at = (
        datetime.now()
        .astimezone()
    )

    published["__meta__"] = {
        "initialized_at":
            initialized_at.isoformat()
    }

    save_json_file(
        PUBLISHED_FILE,
        published,
    )

    return (
        initialized_at,
        True,
    )


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
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing."
        )

    if not EITAAYAR_TOKEN:
        raise RuntimeError(
            "EITAAYAR_TOKEN is missing."
        )

    if not EITAA_CHAT_ID:
        raise RuntimeError(
            "EITAA_CHAT_ID is missing."
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

        if (
            sent_count
            >= MAX_NEWS_PER_RUN
        ):
            print(
                "Maximum news per run reached."
            )
            break

        news_id = create_news_id(
            item
        )

        record = published.get(
            news_id,
            {}
        )

        if not isinstance(
            record,
            dict,
        ):
            record = {}

        telegram_message_id = record.get(
            "telegram_message_id"
        )

        eitaa_message_id = record.get(
            "eitaa_message_id"
        )

        fully_published = (
            telegram_message_id
            is not None
            and eitaa_message_id
            is not None
        )

        if fully_published:
            skipped_count += 1
            continue

        collected_at = (
            get_collected_datetime(item)
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

        if collected_at <= initialized_at:
            skipped_count += 1
            continue

        telegram_message = build_message(
            item
        )

        eitaa_message = (
            build_eitaa_message(
                item
            )
        )

        if not telegram_message.strip():
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

        # =========================================
        # Telegram
        # =========================================

        if telegram_message_id is None:

            try:
                telegram_result = (
                    send_to_telegram(
                        telegram_message
                    )
                )

                telegram_message_id = (
                    telegram_result
                    .get(
                        "result",
                        {},
                    )
                    .get(
                        "message_id"
                    )
                )

                published[
                    news_id
                ] = {
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
                    "telegram_message_id":
                        telegram_message_id,
                }

                save_json_file(
                    PUBLISHED_FILE,
                    published,
                )

                print(
                    "Telegram publication "
                    "recorded."
                )

            except Exception as error:

                print(
                    "Telegram publishing failed:",
                    error,
                )

                failed_count += 1
                continue

        else:

            print(
                "Telegram already published "
                "for this news."
            )

        # =========================================
        # Eitaa
        # =========================================

        if eitaa_message_id is None:

            try:
                eitaa_result = (
                    send_to_eitaa(
                        eitaa_message
                    )
                )

                eitaa_message_id = (
                    eitaa_result
                    .get(
                        "result",
                        {},
                    )
                    .get(
                        "message_id"
                    )
                )

                record = published.get(
                    news_id,
                    {},
                )

                if not isinstance(
                    record,
                    dict,
                ):
                    record = {}

                record.update(
                    {
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
                        "published_at":
                            record.get(
                                "published_at",
                                now_iso(),
                            ),
                        "telegram_message_id":
                            telegram_message_id,
                        "eitaa_message_id":
                            eitaa_message_id,
                    }
                )

                published[
                    news_id
                ] = record

                save_json_file(
                    PUBLISHED_FILE,
                    published,
                )

                print(
                    "Eitaa publication "
                    "recorded."
                )

            except Exception as error:

                print(
                    "Eitaa publishing failed:",
                    error,
                )

                failed_count += 1

                # تلگرام قبلاً ثبت شده.
                # اجرای بعدی دوباره تلگرام را
                # ارسال نمی‌کند و فقط ایتا را
                # امتحان می‌کند.

                continue

        else:

            print(
                "Eitaa already published "
                "for this news."
            )

        # =========================================
        # انتشار کامل
        # =========================================

        if (
            telegram_message_id is not None
            and eitaa_message_id is not None
        ):
            sent_count += 1

            print(
                "News successfully published "
                "to Telegram + Eitaa."
            )

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

    if failed_count > 0:
        raise RuntimeError(
            f"{failed_count} publication(s) failed."
        )


if __name__ == "__main__":
    main()
