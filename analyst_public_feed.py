import json
import os
import re
import tempfile

READY_FILE = "analyst_ready.json"
PUBLIC_FILE = "analyst_public.json"
MAX_ITEMS = 100

GOLD_RE = re.compile(r"طلا|سکه|اونس|انس جهانی|حباب|عیار|حمایت|مقاومت|بازار طلا|gold", re.I)
LINK_RE = re.compile(r"https?://t\.me/\S+", re.I)
CTA_RE = re.compile(r"اگر در بازارهای مالی و طلا فعال هستی[\s\S]*", re.I)


def load_list(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a JSON array")
    return [item for item in value if isinstance(item, dict)]


def item_key(item):
    link = str(item.get("link") or "").strip()
    if link:
        return link.rstrip("/")
    return "|".join(str(item.get(k) or "") for k in ("analyst", "title", "collected_at"))


def is_website_analysis(item):
    groups = item.get("market_groups") if isinstance(item.get("market_groups"), list) else []
    matches = item.get("market_matches") if isinstance(item.get("market_matches"), list) else []
    reasons = item.get("analysis_reasons") if isinstance(item.get("analysis_reasons"), list) else []
    analysis_matches = item.get("analysis_matches") if isinstance(item.get("analysis_matches"), list) else []
    body = str(item.get("summary") or item.get("full_text") or "")
    body = CTA_RE.sub("", body)
    core = LINK_RE.sub("", str(item.get("title") or "") + " " + body).strip()
    has_gold = "gold" in groups or any(re.search(r"طلا|سکه|اونس|gold", str(v), re.I) for v in matches)
    reasoned = ("دارای استدلال" in reasons or "دارای توضیح" in reasons
                or any(str(v) != "قیمت" for v in analysis_matches))
    discusses_gold = bool(GOLD_RE.search(core))
    return has_gold and reasoned and discusses_gold and len(core) >= 100


def save_atomic(path, data):
    fd, tmp = tempfile.mkstemp(prefix=".analyst_public_", suffix=".tmp", dir=".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main():
    existing = load_list(PUBLIC_FILE)
    incoming = [x for x in load_list(READY_FILE) if is_website_analysis(x)]
    merged = {}
    for item in existing + incoming:
        merged[item_key(item)] = item
    result = sorted(
        merged.values(),
        key=lambda x: str(x.get("collected_at") or ""),
        reverse=True,
    )[:MAX_ITEMS]
    save_atomic(PUBLIC_FILE, result)
    print(f"Public gold analyses: {len(result)} (new qualified: {len(incoming)})")


if __name__ == "__main__":
    main()
