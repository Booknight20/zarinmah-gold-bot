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

EITAAYAR_TOKEN = os.environ.get(
    "EITAAYAR_TOKEN"
)

EITAA_CHAT_ID = os.environ.get(
    "EITAA_CHAT_ID"
)

EITAA_API_URL = "https://eitaayar.ir/api"


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
        '<a href="https://t.me/Zarimahgold">'
        "🔗 عضویت در کانال تلگرام زرین ماه"
        "</a>"
    )


def build_eitaa_message(item):
    analyst = str(
        item.get(
            "analyst",
            "",
        )
    ).strip()

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

    link = str(
        item.get(
            "link",
            "",
        )
    ).strip()

    return (
        "🌙 زرین ماه\n\n"
        "📊 تحلیل بازار\n\n"
        f"📰 {title}\n\n"
        f"{summary}\n\n"
        f"📌 تحلیلگر: {analyst}\n"
        f"🔗 مشاهده تحلیل کامل:\n{link}\n\n"
        "🌙 برای دنبال‌کردن اخبار و تحلیل‌های بیشتر زرین ماه"
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


def send_to_eitaa(
    message
):
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
        "Sending analyst message to Eitaa..."
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
        "Eitaa analyst message sent successfully."
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

    if not EITAAYAR_TOKEN:
        raise RuntimeError(
            "EITAAYAR_TOKEN is missing."
        )

    if not EITAA_CHAT_ID:
        raise RuntimeError(
            "EITAA_CHAT_ID is missing."
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

        if (
            sent
            >= MAX_ANALYSES_PER_RUN
        ):
            print(
                "Maximum analyses per run reached."
            )
            break

        analysis_id = create_id(
            item
        )

        record = published.get(
            analysis_id,
            {},
        )

        if not isinstance(
            record,
            dict,
        ):
            record = {}

        telegram_message_id = (
            record.get(
                "telegram_message_id"
            )
        )

        eitaa_message_id = (
            record.get(
                "eitaa_message_id"
            )
        )

        fully_published = (
            telegram_message_id is not None
            and eitaa_message_id is not None
        )

        if fully_published:
            print(
                "Analysis already published "
                "to Telegram and Eitaa:"
            )
            print(
                item.get(
                    "title",
                    "",
                )
            )
            continue

        telegram_message = build_message(
            item
        )

        eitaa_message = build_eitaa_message(
            item
        )

        if not telegram_message.strip():
            print(
                "Empty Telegram message. Skipping."
            )
            continue

        if not eitaa_message.strip():
            print(
                "Empty Eitaa message. Skipping."
            )
            continue

        print()
        print(
            "Publishing analysis:",
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
                    analysis_id
                ] = {
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
                    "telegram_message_id":
                        telegram_message_id,
                }

                save_json(
                    PUBLISHED_FILE,
                    published,
                )

                print(
                    "Telegram publication recorded."
                )

            except Exception as error:
                print(
                    "Telegram publishing failed:",
                    error,
                )

                failed += 1
                continue

        else:

            print(
                "Telegram already published "
                "for this analysis."
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
                    analysis_id,
                    {},
                )

                if not isinstance(
                    record,
                    dict,
                ):
                    record = {}

                record.update(
                    {
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
                    analysis_id
                ] = record

                save_json(
                    PUBLISHED_FILE,
                    published,
                )

                print(
                    "Eitaa publication recorded."
                )

            except Exception as error:

                print(
                    "Eitaa publishing failed:",
                    error,
                )

                failed += 1

                # تلگرام قبلاً ثبت شده.
                # اجرای بعدی دوباره تلگرام را
                # نمی‌فرستد و فقط ایتا را امتحان می‌کند.

                continue

        else:

            print(
                "Eitaa already published "
                "for this analysis."
            )

        # =========================================
        # هر دو مقصد موفق
        # =========================================

        if (
            telegram_message_id is not None
            and eitaa_message_id is not None
        ):
            sent += 1

            print(
                "Analysis successfully published "
                "to Telegram + Eitaa."
            )

    print()
    print(
        "==================================="
    )

    print(
        "Analyst publishing finished."
    )

    print(
        "==================================="
    )

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
