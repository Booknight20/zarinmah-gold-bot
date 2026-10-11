# -*- coding: utf-8 -*-

import os
import sys

import requests

from daily_analysis import build_message
from capital_flow import build_capital_flow_section


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
EITAAYAR_TOKEN = os.environ.get("EITAAYAR_TOKEN")
EITAA_CHAT_ID = os.environ.get("EITAA_CHAT_ID")

TELEGRAM_CHANNEL = "@ZarinMahGold"
TELEGRAM_CHANNEL_URL = "https://t.me/ZarinMahGold"
EITAA_API_URL = "https://eitaayar.ir/api"

CHANNEL_PROMO = (
    "🌙 زرین ماه | طلای کم‌اجرت\n"
    "تحلیل بازار و آگهی‌های طلای کم‌اجرت را دنبال کنید.\n"
    "کانال تلگرام: " + TELEGRAM_CHANNEL_URL
)


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
        "reply_markup": {
            "inline_keyboard": [[
                {
                    "text": "View Channel",
                    "url": TELEGRAM_CHANNEL_URL,
                }
            ]]
        },
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
        fail(f"Telegram request failed: {repr(error)}")

    print("Telegram HTTP status:", response.status_code)
    print("Telegram response:", response.text)

    if response.status_code != 200:
        fail("Telegram returned an HTTP error.")

    try:
        data = response.json()
    except ValueError:
        fail("Telegram returned invalid JSON.")

    if data.get("ok") is not True:
        fail(f"Telegram rejected the message: {data}")

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
        fail(f"Eitaa request failed: {repr(error)}")

    print("Eitaa HTTP status:", response.status_code)
    print("Eitaa response:", response.text)

    if response.status_code != 200:
        fail("Eitaa returned an HTTP error.")

    try:
        data = response.json()
    except ValueError:
        fail("Eitaa returned invalid JSON.")

    if data.get("ok") is not True:
        fail(f"Eitaa rejected the message: {data}")

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

    if not message or not message.strip():
        fail("Generated daily analysis is empty.")

    print("Building capital flow section...")

    try:
        capital_flow_section = build_capital_flow_section()

        if capital_flow_section and capital_flow_section.strip():
            message = (
                message.rstrip()
                + "\n\n"
                + capital_flow_section.strip()
            )
            print("Capital flow section added successfully.")
        else:
            print("Capital flow section is empty.")

    except Exception as error:
        print(
            "Capital flow section failed:",
            repr(error),
        )

        message += (
            "\n\n"
            "💧 گزارش جریان نقدینگی بازار\n"
            "⚠️ دریافت اطلاعات جریان پول در این اجرا "
            "با خطا مواجه شد."
        )

    # The channel promotion is appended only after the analysis and capital-flow section,
    # so it remains the final part of the message on both Telegram and Eitaa.
    message = message.rstrip() + "\n\n" + CHANNEL_PROMO

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

    print("Saved daily_message.txt successfully.")

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
