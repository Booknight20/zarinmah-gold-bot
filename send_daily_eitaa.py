import json
import os
import sys
from pathlib import Path

import requests


EITAAYAR_TOKEN = os.environ.get("EITAAYAR_TOKEN")
EITAA_CHAT_ID = os.environ.get("EITAA_CHAT_ID")

MESSAGE_FILE = Path("daily_message.txt")

API_URL = "https://eitaayar.ir/api"


def fail(message):
    print(message)
    sys.exit(1)


def main():
    print("===================================")
    print("ZarinMah Eitaa Daily Sender")
    print("===================================")

    if not EITAAYAR_TOKEN:
        fail("ERROR: EITAAYAR_TOKEN is missing.")

    if not EITAA_CHAT_ID:
        fail("ERROR: EITAA_CHAT_ID is missing.")

    if not MESSAGE_FILE.exists():
        fail(
            "ERROR: daily_message.txt was not created."
        )

    message = MESSAGE_FILE.read_text(
        encoding="utf-8"
    ).strip()

    if not message:
        fail(
            "ERROR: daily_message.txt is empty."
        )

    print(
        "Message length:",
        len(message),
    )

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
        "Eitaa chat ID:",
        EITAA_CHAT_ID,
    )

    try:
        response = requests.post(
            url,
            data=payload,
            timeout=30,
        )
    except requests.RequestException as error:
        fail(
            f"Eitaa request failed: {error}"
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
        fail(
            "Eitaa returned HTTP error."
        )

    try:
        data = response.json()
    except ValueError:
        fail(
            "Eitaa returned invalid JSON."
        )

    if data.get("ok") is not True:
        fail(
            "Eitaa did not confirm successful delivery."
        )

    print(
        "==================================="
    )

    print(
        "SUCCESS: Daily analysis sent to Eitaa."
    )

    print(
        "Eitaa result:",
        data.get("result"),
    )

    print(
        "==================================="
    )


if __name__ == "__main__":
    main()
