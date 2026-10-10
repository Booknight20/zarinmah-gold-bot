
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "promo_groups.json"
STATE_FILE = BASE_DIR / "promo_sent.json"
TEHRAN = ZoneInfo("Asia/Tehran")
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
REQUEST_TIMEOUT = 25


def load_json(path, default):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            f"خواندن فایل {path.name} ناموفق بود: {exc}"
        ) from exc


def save_json(path, data):
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def week_key(now):
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def send_message(token, chat_id, text, button_text, channel_url):
    url = TELEGRAM_API.format(token=token, method="sendMessage")

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [[
                {
                    "text": button_text,
                    "url": channel_url
                }
            ]]
        }
    }

    response = requests.post(
        url,
        json=payload,
        timeout=REQUEST_TIMEOUT
    )

    try:
        result = response.json()
    except ValueError:
        result = {}

    if not response.ok or not result.get("ok"):
        description = result.get(
            "description",
            response.text[:500]
        )
        raise RuntimeError(
            f"Telegram API error for {chat_id}: {description}"
        )

    return result["result"].get("message_id")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

    if not token:
        print(
            "ERROR: secret TELEGRAM_BOT_TOKEN is not set.",
            file=sys.stderr
        )
        return 2

    config = load_json(CONFIG_FILE, {})

    if not config.get("enabled", False):
        print("Promotion broadcast is disabled.")
        return 0

    channel_url = str(
        config.get(
            "channel_url",
            "https://t.me/ZarinMahGold"
        )
    ).strip()

    message = str(config.get("message", "")).strip()

    button_text = str(
        config.get(
            "button_text",
            "عضویت در کانال زرین ماه"
        )
    ).strip()

    if not channel_url.startswith("https://t.me/"):
        print("ERROR: Invalid channel URL.", file=sys.stderr)
        return 2

    if not message:
        print("ERROR: Promotion message is empty.", file=sys.stderr)
        return 2

    groups = [
        group
        for group in config.get("groups", [])
        if group.get("enabled")
        and str(group.get("chat_id", "")).strip()
    ]

    if not groups:
        print("No enabled group IDs found.")
        return 0

    now = datetime.now(TEHRAN)
    current_week = week_key(now)

    state = load_json(STATE_FILE, {"sent": {}})
    sent_records = state.setdefault("sent", {})

    errors = 0
    sent_count = 0

    print(
        f"Promotion run: {now:%Y-%m-%d %H:%M:%S %Z}; "
        f"week={current_week}"
    )

    for group in groups:
        chat_id = str(group["chat_id"]).strip()
        group_name = str(group.get("name", chat_id))
        key = f"{chat_id}:{current_week}"

        if sent_records.get(key):
            print(
                f"SKIP {group_name}: already sent this week."
            )
            continue

        try:
            message_id = send_message(
                token=token,
                chat_id=chat_id,
                text=message,
                button_text=button_text,
                channel_url=channel_url
            )

            sent_records[key] = {
                "chat_id": chat_id,
                "group_name": group_name,
                "sent_at": now.isoformat(),
                "message_id": message_id
            }

            save_json(STATE_FILE, state)
            sent_count += 1

            print(
                f"SENT {group_name} ({chat_id}), "
                f"message_id={message_id}"
            )

        except (
            requests.RequestException,
            RuntimeError,
            KeyError
        ) as exc:
            errors += 1
            print(
                f"FAILED {group_name} ({chat_id}): {exc}",
                file=sys.stderr
            )

    print(f"Finished. sent={sent_count}, failed={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
