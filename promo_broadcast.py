
import html
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

BASE_DIR = Path(__file__).resolve().parent
TARGETS_FILE = BASE_DIR / "promo_targets.json"
STATE_FILE = BASE_DIR / "promo_sent.json"
TEHRAN = ZoneInfo("Asia/Tehran")
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
EITAA_API = "https://eitaayar.ir/api/{token}/sendMessage"
TIMEOUT = 25


def load_json(path, default):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"خطا در خواندن {path.name}: {exc}"
        ) from exc


def save_json(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    temp.replace(path)


def week_key(now):
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def check_response(response, platform):
    try:
        data = response.json()
    except ValueError:
        data = {}

    if not response.ok:
        raise RuntimeError(
            f"{platform} HTTP {response.status_code}: "
            f"{response.text[:400]}"
        )

    if data.get("ok") is False or data.get("error"):
        reason = (
            data.get("description")
            or data.get("error")
            or str(data)
        )
        raise RuntimeError(f"{platform}: {reason}")

    return data


def send_telegram(token, chat_id, message, button_text, channel_url):
    response = requests.post(
        TELEGRAM_API.format(token=token, method="sendMessage"),
        json={
            "chat_id": chat_id,
            "text": message,
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
        },
        timeout=TIMEOUT
    )
    return check_response(response, "Telegram")


def send_eitaa(token, chat_id, message, button_text, channel_url):
    # در ایتا لینک به شکل متن فرستاده می‌شود.
    # توکن معتبر EitaaYar و دسترسی انتشار لازم است.
    plain_text = html.unescape(
        re.sub(r"<[^>]+>", "", message)
    )
    text = (
        f"{plain_text}\n\n"
        f"{button_text}: {channel_url}"
    )

    response = requests.post(
        EITAA_API.format(token=token),
        data={
            "chat_id": chat_id,
            "text": text
        },
        timeout=TIMEOUT
    )
    return check_response(response, "Eitaa")


def main():
    config = load_json(TARGETS_FILE, {})

    if not config.get("enabled", False):
        print("ارسال تبلیغات غیرفعال است.")
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
        print("خطا: لینک تلگرام معتبر نیست.", file=sys.stderr)
        return 2

    if not message:
        print("خطا: متن تبلیغ خالی است.", file=sys.stderr)
        return 2

    targets = [
        target
        for target in config.get("targets", [])
        if target.get("enabled") is True
        and target.get("permission_confirmed") is True
        and str(target.get("chat_id", "")).strip()
    ]

    if not targets:
        print("هیچ مقصد مجاز و فعالی تنظیم نشده است.")
        return 0

    tg_token = os.environ.get(
        "TELEGRAM_BOT_TOKEN", ""
    ).strip()

    eitaa_token = os.environ.get(
        "EITAAYAR_TOKEN", ""
    ).strip()

    now = datetime.now(TEHRAN)
    current_week = week_key(now)

    state = load_json(STATE_FILE, {"sent": {}})
    sent = state.setdefault("sent", {})

    delivered = 0
    failed = 0

    print(
        f"شروع تبلیغات: {now.isoformat()} "
        f"| هفته {current_week}"
    )

    for target in targets:
        platform = str(
            target.get("platform", "telegram")
        ).lower().strip()

        chat_id = str(target["chat_id"]).strip()
        name = str(target.get("name", chat_id))
        key = f"{platform}:{chat_id}:{current_week}"

        if sent.get(key):
            print(f"رد شد؛ قبلاً ارسال شده: {name}")
            continue

        try:
            if platform == "telegram":
                if not tg_token:
                    raise RuntimeError(
                        "Secret با نام TELEGRAM_BOT_TOKEN تنظیم نشده است."
                    )

                send_telegram(
                    tg_token,
                    chat_id,
                    message,
                    button_text,
                    channel_url
                )

            elif platform == "eitaa":
                if not eitaa_token:
                    raise RuntimeError(
                        "Secret با نام EITAAYAR_TOKEN تنظیم نشده است."
                    )

                send_eitaa(
                    eitaa_token,
                    chat_id,
                    message,
                    button_text,
                    channel_url
                )

            else:
                raise RuntimeError(
                    f"پیام‌رسان ناشناخته: {platform}"
                )

            sent[key] = {
                "platform": platform,
                "chat_id": chat_id,
                "name": name,
                "sent_at": now.isoformat(),
                "week": current_week
            }

            save_json(STATE_FILE, state)
            delivered += 1
            print(f"ارسال موفق: {platform} | {name}")

        except (
            requests.RequestException,
            RuntimeError,
            KeyError
        ) as exc:
            failed += 1
            print(
                f"خطا در {name}: {exc}",
                file=sys.stderr
            )

    print(
        f"پایان کار: موفق={delivered}، ناموفق={failed}"
    )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
