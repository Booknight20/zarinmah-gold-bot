import json
import os
import sys
from pathlib import Path
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = "@ZarinMahGold"
CHANNEL_USERNAME = "ZarinMahGold"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
NEWS_FILE = Path("news_published.json")
ANALYST_FILE = Path("analyst_published.json")
STATE_FILE = Path("channel_archive_state.json")
PAGE_SIZE = 15

CATEGORIES = {
    "news": {
        "title": "📰 آرشیو اخبار بازار زرین ماه",
        "file": NEWS_FILE,
        "empty": "هنوز خبری در آرشیو ثبت نشده است.",
    },
    "analysis": {
        "title": "📈 آرشیو تحلیل‌های روزانه زرین ماه",
        "file": ANALYST_FILE,
        "empty": "هنوز تحلیلی در آرشیو ثبت نشده است.",
    },
}


def telegram_request(method, payload):
    response = requests.post(
        f"{API_URL}/{method}", json=payload, timeout=30
    )
    try:
        data = response.json()
    except ValueError as error:
        raise RuntimeError(
            f"Telegram returned invalid JSON ({response.status_code})."
        ) from error
    if not response.ok or not data.get("ok"):
        description = data.get("description", response.text)
        # Telegram returns this when an edit would make no changes.
        if method.startswith("editMessage") and "message is not modified" in str(description).lower():
            return True
        raise RuntimeError(f"Telegram API error in {method}: {description}")
    return data["result"]


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError) as error:
        raise RuntimeError(f"Could not read {path}: {error}") from error


def save_state(state):
    temp_path = STATE_FILE.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
    temp_path.replace(STATE_FILE)


def get_records(path, category):
    data = load_json(path, {})
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a JSON object.")

    records = []
    seen_ids = set()
    for key, item in data.items():
        if key == "__meta__" or not isinstance(item, dict):
            continue
        raw_id = item.get("telegram_message_id")
        try:
            message_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if message_id in seen_ids:
            continue
        seen_ids.add(message_id)

        title = str(item.get("title") or "").strip()
        if not title and isinstance(item.get("item"), dict):
            title = str(item["item"].get("title") or "").strip()
        if not title and category == "analysis":
            analyst = str(item.get("analyst") or "تحلیلگر بازار").strip()
            title = f"تحلیل منتشرشده از {analyst}"
        if not title:
            title = "خبر بازار"

        # Telegram button labels are limited to 64 characters.
        title = " ".join(title.split())
        if len(title) > 60:
            title = title[:57].rstrip() + "…"

        records.append({
            "message_id": message_id,
            "title": title,
            "published_at": str(item.get("published_at") or item.get("telegram_sent_at") or ""),
        })

    # Telegram channel message IDs increase over time; this reliably places newest first.
    records.sort(key=lambda record: record["message_id"], reverse=True)
    return records


def page_text(category, page_number, page_count, records):
    title = CATEGORIES[category]["title"]
    if not records:
        return f"{title}\n\n{CATEGORIES[category]['empty']}\n\nزرین ماه | طلای کم‌اجرت"
    return (
        f"{title}\n\n"
        f"📚 صفحه {page_number} از {page_count}\n"
        "مطالب جدیدتر در ابتدای فهرست قرار دارند. برای بازکردن هر مطلب، دکمه آن را بزنید.\n\n"
        "زرین ماه | طلای کم‌اجرت"
    )


def build_markup(category, page_number, page_count, records, page_ids):
    rows = []
    for record in records:
        rows.append([{
            "text": record["title"],
            "url": f"https://t.me/{CHANNEL_USERNAME}/{record['message_id']}",
        }])

    nav = []
    ids = page_ids[category]["message_ids"]
    if page_number > 1:
        nav.append({
            "text": "⬅️ مطالب جدیدتر",
            "url": f"https://t.me/{CHANNEL_USERNAME}/{ids[page_number - 2]}",
        })
    if page_number < page_count:
        nav.append({
            "text": "مطالب قدیمی‌تر ➡️",
            "url": f"https://t.me/{CHANNEL_USERNAME}/{ids[page_number]}",
        })
    if nav:
        rows.append(nav)
    return {"inline_keyboard": rows}


def update_category(category, records, state):
    pages = [records[i:i + PAGE_SIZE] for i in range(0, len(records), PAGE_SIZE)]
    if not pages:
        pages = [[]]
    category_state = state.setdefault(category, {"message_ids": []})
    page_ids = category_state.setdefault("message_ids", [])

    # Create stable archive page messages when a category grows.
    while len(page_ids) < len(pages):
        page_number = len(page_ids) + 1
        result = telegram_request("sendMessage", {
            "chat_id": CHANNEL,
            "text": f"{CATEGORIES[category]['title']}\n\nدر حال آماده‌سازی آرشیو…",
            "disable_web_page_preview": True,
        })
        page_ids.append(int(result["message_id"]))
        save_state(state)
        print(f"Created {category} archive page {page_number}: {page_ids[-1]}")

    # Keep old extra pages available but clearly mark them if the data set shrinks.
    for index, page_id in enumerate(page_ids):
        page_number = index + 1
        page_records = pages[index] if index < len(pages) else []
        text = page_text(category, page_number, len(pages), page_records)
        markup = build_markup(category, page_number, len(pages), page_records, state)
        telegram_request("editMessageText", {
            "chat_id": CHANNEL,
            "message_id": page_id,
            "text": text,
            "reply_markup": markup,
            "disable_web_page_preview": True,
        })
        print(f"Updated {category} archive page {page_number}: {page_id}")

    category_state["updated_at"] = __import__("datetime").datetime.now().astimezone().isoformat()
    save_state(state)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing from GitHub Secrets.")

    state = load_json(STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}

    for category, config in CATEGORIES.items():
        records = get_records(config["file"], category)
        print(f"{category}: {len(records)} Telegram posts found.")
        update_category(category, records, state)

    print("News and analysis archives updated successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)
