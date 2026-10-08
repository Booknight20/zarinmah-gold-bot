import os
import sys

import requests

from daily_analysis import build_message


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
EITAAYAR_TOKEN = os.environ.get("EITAAYAR_TOKEN")
EITAA_CHAT_ID = os.environ.get("EITAA_CHAT_ID")

TELEGRAM_CHANNEL = "@ZarinMahGold"
EITAA_API_URL = "https://eitaayar.ir/api"


def fail(message):
    print(message)
    sys.exit(1)


def send_to_telegram(message):
    if not TELEGRAM_BOT_TOKEN:
        fail("ERROR: TELEGRAM_BOT_TOKEN is missing.")

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHANNEL,
        "text": message,
    }

    print("===================================")
    print("Sending daily analysis to Telegram...")
    print("Telegram channel:", TELEGRAM_CHANNEL)
    print("Message length:", len(message))

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as error:
        fail(
            f"Telegram request failed: {repr(error)}"
        )

    print("Telegram HTTP status:", response.status_code)
    print("Telegram response:", response.text)

    if response.status_code != 200:
        fail(
            "Telegram returned an HTTP error."
        )

    try:
        data = response.json()
    except ValueError:
        fail(
            "Telegram returned invalid JSON."
        )

    if data.get("ok") is not True:
        fail(
            f"Telegram rejected the message: {data}"
        )

    print("Telegram API accepted the message.")
    print("===================================")


def send_to_eitaa(message):
    if not EITAAYAR_TOKEN:
        fail("ERROR: EITAAYAR_TOKEN is missing.")

    if not EITAA_CHAT_ID:
        fail("ERROR: EITAA_CHAT_ID is missing.")

    url = (
        f"{EITAA_API_URL}/"
        f"{EITAAYAR_TOKEN}/"
        "sendMessage"
    )

    payload = {
        "chat_id": EITAA_CHAT_ID,
        "text": message,
    }

    print("===================================")
    print("Sending daily analysis to Eitaa...")
    print("Eitaa chat ID:", EITAA_CHAT_ID)
    print("Message length:", len(message))
    print(
        "Request URL: "
        "https://eitaayar.ir/api/***/sendMessage"
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

    print("Eitaa HTTP status:", response.status_code)
    print("Eitaa response:", response.text)

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

    print("Eitaa API accepted the message.")
    print("===================================")


def main():
    print("")
    print("###################################")
    print("# ZarinMah Daily Sender")
    print("###################################")
    print("")

    print("Building daily analysis...")

    try:
        message = build_message()
    except Exception as error:
        fail(
            f"Could not build daily analysis: {repr(error)}"
        )

    if not message.strip():
        fail(
            "Generated daily analysis is empty."
        )

    print("")
    print("Generated message:")
    print("------------------")
    print(message)
    print("------------------")
    print("")

    with open(
        "daily_message.txt",
        "w",
        encoding="utf-8",
    ) as file:
        file.write(message)

    print(
        "Saved daily_message.txt successfully."
    )

    send_to_telegram(message)
    send_to_eitaa(message)

    print("")
    print("###################################")
    print("# SUCCESS")
    print("# Daily analysis sent to Telegram")
    print("# and Eitaa successfully.")
    print("###################################")
    print("")


if __name__ == "__main__":
    main()
