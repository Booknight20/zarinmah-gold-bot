import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


EITAAYAR_TOKEN = os.environ.get(
    "EITAAYAR_TOKEN"
)

EITAA_CHAT_ID = os.environ.get(
    "EITAA_CHAT_ID"
)

FORCE_EITAA_SEND = (
    os.environ.get(
        "FORCE_EITAA_SEND",
        "false",
    ).lower()
    == "true"
)

MESSAGE_FILE = "daily_message.txt"
STATUS_FILE = "send_status.json"

TEHRAN = ZoneInfo("Asia/Tehran")

API_URL = "https://eitaayar.ir/api"


def fail(message):
    print(message)
    sys.exit(1)


def load_status():
    if not os.path.exists(STATUS_FILE):
        return {
            "hourly": {},
            "daily": {},
            "watchdog": {},
            "daily_telegram": {},
            "daily_eitaa": {},
        }

    try:
        with open(
            STATUS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            data = {}

        data.setdefault(
            "hourly",
            {},
        )

        data.setdefault(
            "daily",
            {},
        )

        data.setdefault(
            "watchdog",
            {},
        )

        data.setdefault(
            "daily_telegram",
            {},
        )

        data.setdefault(
            "daily_eitaa",
            {},
        )

        return data

    except Exception as error:
        print(
            "Could not load status:",
            repr(error),
        )

        return {
            "hourly": {},
            "daily": {},
            "watchdog": {},
            "daily_telegram": {},
            "daily_eitaa": {},
        }


def save_status(status):
    with open(
        STATUS_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            status,
            file,
            ensure_ascii=False,
            indent=2,
        )


def save_eitaa_status(slot):
    status = load_status()

    status["daily_eitaa"] = {
        "slot": slot,
        "sent_at": datetime.now(
            TEHRAN
        ).isoformat(),
    }

    telegram_status = status.get(
        "daily_telegram",
        {},
    )

    telegram_sent = (
        isinstance(
            telegram_status,
            dict,
        )
        and telegram_status.get(
            "slot"
        )
        == slot
    )

    if telegram_sent:
        status["daily"] = {
            "slot": slot,
            "sent_at": datetime.now(
                TEHRAN
            ).isoformat(),
        }

    save_status(status)

    print(
        "Eitaa daily status saved:",
        slot,
    )


def main():

    print(
        "==================================="
    )

    print(
        "ZarinMah Daily Eitaa Sender"
    )

    print(
        "==================================="
    )

    if not EITAAYAR_TOKEN:
        fail(
            "ERROR: EITAAYAR_TOKEN is missing."
        )

    if not EITAA_CHAT_ID:
        fail(
            "ERROR: EITAA_CHAT_ID is missing."
        )

    if not os.path.exists(
        MESSAGE_FILE
    ):
        fail(
            "ERROR: daily_message.txt does not exist."
        )

    with open(
        MESSAGE_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        message = file.read().strip()

    if not message:
        fail(
            "ERROR: daily_message.txt is empty."
        )

    now = datetime.now(TEHRAN)

    current_slot = now.strftime(
        "%Y-%m-%d"
    )

    print(
        "Tehran date:",
        current_slot,
    )

    print(
        "Eitaa chat ID:",
        EITAA_CHAT_ID,
    )

    print(
        "Message length:",
        len(message),
        "characters",
    )

    print(
        "Force Eitaa send:",
        FORCE_EITAA_SEND,
    )

    # -----------------------------------------------------
    # جلوگیری از ارسال تکراری
    # -----------------------------------------------------

    status = load_status()

    already_sent = (
        status.get(
            "daily_eitaa",
            {},
        ).get(
            "slot"
        )
        == current_slot
    )

    if already_sent and not FORCE_EITAA_SEND:
        print(
            "Eitaa daily message was already marked "
            "as sent for today."
        )

        print(
            "Use FORCE_EITAA_SEND=true for a manual retry."
        )

        return

    # -----------------------------------------------------
    # آدرس API
    # -----------------------------------------------------

    url = (
        f"{API_URL}/"
        f"{EITAAYAR_TOKEN}/"
        "sendMessage"
    )

    payload = {
        "chat_id": EITAA_CHAT_ID,
        "text": message,
    }

    print(
        "Sending daily analysis to Eitaa..."
    )

    print(
        "Request URL:",
        "https://eitaayar.ir/api/***/sendMessage",
    )

    try:
        response = requests.post(
            url,
            data=payload,
            timeout=30,
        )

    except requests.RequestException as error:
        fail(
            f"Eitaa request failed: {repr(error)}"
        )

    # -----------------------------------------------------
    # پاسخ API
    # -----------------------------------------------------

    print(
        "Eitaa HTTP status:",
        response.status_code,
    )

    print(
        "Eitaa response:",
        response.text,
    )

    if response.status_code != 200:
        fail(
            "Eitaa returned an HTTP error."
        )

    try:
        data = response.json()

    except ValueError:
        fail(
            "Eitaa returned invalid JSON."
        )

    if data.get("ok") is not True:
        fail(
            f"Eitaa rejected the message: {data}"
        )

    # -----------------------------------------------------
    # موفقیت واقعی
    # -----------------------------------------------------

    print(
        "Eitaa API accepted the message."
    )

    save_eitaa_status(
        current_slot
    )

    print(
        "==================================="
    )

    print(
        "SUCCESS: Daily analysis sent to Eitaa."
    )

    print(
        "==================================="
    )


if __name__ == "__main__":
    main()
