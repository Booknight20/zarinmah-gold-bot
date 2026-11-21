"""Build the website-only public analysis archive.

This script scans the five approved public Telegram analyst channels for the
latest seven days. It does not publish to Telegram or Eitaa and does not
modify analyst_ready.json / analyst_published.json.
"""
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

import analyst_bot

PUBLIC_FILE = "analyst_public.json"
MAX_AGE = timedelta(days=7)
MAX_ITEMS = 10
MAX_PER_ANALYST = 3
MAX_PAGES_PER_SOURCE = 25
REQUEST_TIMEOUT = 25
USER_AGENT = (
    "Mozilla/5.0 (compatible; ZarinMahPublicArchive/1.0; "
    "+https://t.me/ZarinMahGold)"
)


def parse_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def item_key(item):
    link = str(item.get("link") or "").strip().rstrip("/")
    if link:
        return link
    return "|".join(str(item.get(k) or "") for k in ("analyst", "title", "collected_at"))


def load_list(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a JSON array")
    return [item for item in value if isinstance(item, dict)]


def save_atomic(path, data):
    fd, temporary = tempfile.mkstemp(prefix=".analyst_public_", suffix=".tmp", dir=".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def parse_posts(page_html, channel):
    soup = BeautifulSoup(page_html, "html.parser")
    posts = []
    ids = []

    for node in soup.select(".tgme_widget_message"):
        post_id = str(node.get("data-post") or "").strip()
        date_node = node.select_one(".tgme_widget_message_date time[datetime]")
        text_node = node.select_one(".tgme_widget_message_text")

        if not post_id or not date_node or not text_node:
            continue

        published = parse_datetime(date_node.get("datetime"))
        if not published:
            continue

        link_node = node.select_one(".tgme_widget_message_date")
        link = str(link_node.get("href") or "").strip() if link_node else ""
        if not link:
            message_number = post_id.rsplit("/", 1)[-1]
            link = f"https://t.me/{channel}/{message_number}"

        message_text = analyst_bot.clean_html(str(text_node))
        if not message_text:
            continue

        match = re.search(r"/(\\d+)$", post_id)
        if match:
            ids.append(int(match.group(1)))

        posts.append({
            "link": analyst_bot.compact_telegram_link(link),
            "text": message_text,
            "published_at": published,
        })

    return posts, ids


def fetch_recent_posts(channel, cutoff):
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    collected = {}
    before_id = None
    oldest_seen = None

    for page_number in range(MAX_PAGES_PER_SOURCE):
        url = f"https://t.me/s/{channel}"
        if before_id:
            url += "?" + urlencode({"before": before_id})

        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        posts, ids = parse_posts(response.text, channel)

        if not posts or not ids:
            break

        for post in posts:
            key = post["link"]
            if key not in collected:
                collected[key] = post
            published = post["published_at"]
            if oldest_seen is None or published < oldest_seen:
                oldest_seen = published

        page_oldest = min(post["published_at"] for post in posts)
        if page_oldest < cutoff:
            break

        next_before = min(ids)
        if before_id == next_before:
            break
        before_id = next_before

    return list(collected.values()), oldest_seen


def build_public_item(source_name, post, evaluation):
    item = analyst_bot.make_item(source_name, post, evaluation)
    published_at = post["published_at"].isoformat()
    item["published_at"] = published_at
    # The website sorts by collected_at; use the original post time so the
    # seven-day window and ordering remain accurate on later workflow runs.
    item["collected_at"] = published_at
    return item


def main():
    now = datetime.now(timezone.utc)
    cutoff = now - MAX_AGE
    merged = {}

    # Keep only still-fresh records from the current website archive.
    for item in load_list(PUBLIC_FILE):
        timestamp = parse_datetime(item.get("published_at") or item.get("collected_at"))
        if timestamp and cutoff <= timestamp <= now + timedelta(minutes=10):
            merged[item_key(item)] = item

    stats = {}
    for source_name, config in analyst_bot.ANALYSTS.items():
        channel = config["channel"]
        print(f"Scanning {source_name} (@{channel})")
        try:
            posts, oldest = fetch_recent_posts(channel, cutoff)
        except Exception as error:
            stats[source_name] = {"error": str(error)}
            print(f"Source scan failed: {source_name}: {error}")
            continue

        accepted = 0
        for post in posts:
            published = post["published_at"]
            if published < cutoff or published > now + timedelta(minutes=10):
                continue

            evaluation = analyst_bot.evaluate_analysis(post["text"])
            if not evaluation.get("relevant"):
                continue

            item = build_public_item(source_name, post, evaluation)
            merged[item_key(item)] = item
            accepted += 1

        stats[source_name] = {
            "posts_scanned": len(posts),
            "qualified": accepted,
            "oldest_post": oldest.isoformat() if oldest else None,
        }
        print(f"  scanned={len(posts)} qualified={accepted}")

    # Prefer recent posts; score breaks ties. Limit each source to three
    # entries so the front page is not dominated by a single channel.
    candidates = sorted(
        merged.values(),
        key=lambda item: (
            parse_datetime(item.get("published_at") or item.get("collected_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
            int(item.get("analysis_score") or 0),
        ),
        reverse=True,
    )

    result = []
    per_source = {}
    used = set()
    for item in candidates:
        key = item_key(item)
        source = str(item.get("analyst") or item.get("source") or "نامشخص")
        if key in used or per_source.get(source, 0) >= MAX_PER_ANALYST:
            continue
        result.append(item)
        used.add(key)
        per_source[source] = per_source.get(source, 0) + 1
        if len(result) >= MAX_ITEMS:
            break

    save_atomic(PUBLIC_FILE, result)
    print(f"Website-only public analyses: {len(result)}")
    print("Source scan summary:", json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
