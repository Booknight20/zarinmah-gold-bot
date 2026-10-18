
def fetch_channel_posts(
    channel,
    max_pages=8,
):
    posts = []
    seen_links = set()
    before = None

    # برای تشخیص قالب واقعی پیام قیمت طلا
    debug_gold18 = channel.lower() == "navasanchannel"

    for page_number in range(
        1,
        max_pages + 1,
    ):
        url = f"https://t.me/s/{channel}"

        if before:
            url += f"?before={before}"

        print(
            f"Reading {channel} "
            f"page {page_number}..."
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        wrappers = soup.select(
            "div.tgme_widget_message_wrap"
        )

        if not wrappers:
            print(
                "No Telegram message wrappers found "
                "on this page."
            )
            break

        page_posts = []

        for wrapper in wrappers:
            text_node = wrapper.select_one(
                "div.tgme_widget_message_text"
            )

            date_node = wrapper.select_one(
                "a.tgme_widget_message_date"
            )

            if not text_node or not date_node:
                continue

            text = clean_text(
                text_node.get_text(
                    "\n",
                    strip=True,
                )
            )

            link = date_node.get(
                "href",
                "",
            )

            if not text or not link:
                continue

            if link in seen_links:
                continue

            seen_links.add(link)

            # ثبت زمان انتشار پست
            time_node = date_node.select_one("time")
            posted_at = None

            if time_node:
                posted_at = time_node.get("datetime")

            if not posted_at:
                posted_at = date_node.get("datetime")

            message_id = get_message_id(link)

            page_posts.append(
                {
                    "text": text,
                    "link": link,
                    "message_id": message_id,
                    "posted_at": posted_at,
                }
            )

            # بررسی متن واقعی پیام‌های کانال نوسان
            if debug_gold18:
                normalized_text = normalize_digits(
                    clean_text(text)
                )

                normalized_text = (
                    normalized_text
                    .replace("ي", "ی")
                    .replace("ك", "ک")
                )

                if re.search(
                    r"طلای\s*18\s*عیار",
                    normalized_text,
                    flags=re.IGNORECASE,
                ):
                    print(
                        "========== DEBUG NAVASAN GOLD18 =========="
                    )
                    print("Message ID:", message_id)
                    print("Message link:", link)
                    print("Posted at:", posted_at)
                    print(
                        "Extracted text:",
                        repr(text),
                    )

                    # آزمایش مستقیم استخراج قیمت
                    for line in normalized_text.splitlines():
                        if re.search(
                            r"طلای\s*18\s*عیار",
                            line,
                            flags=re.IGNORECASE,
                        ):
                            print(
                                "Gold line:",
                                repr(line),
                            )
                            print(
                                "Parsed price:",
                                extract_navasan_line_price(line),
                            )

                    print(
                        "=========================================="
                    )

        print(
            "Posts found on page:",
            len(page_posts),
        )

        if not page_posts:
            break

        posts.extend(page_posts)

        ids = [
            post["message_id"]
            for post in page_posts
            if post["message_id"] > 0
        ]

        if not ids:
            break

        before = str(min(ids))

    posts.sort(
        key=lambda item: item["message_id"],
        reverse=True,
    )

    print(
        f"Total posts collected from "
        f"{channel}: {len(posts)}"
    )

    if posts:
        print(
            "Newest message ID:",
            posts[0]["message_id"],
        )
        print(
            "Newest message link:",
            posts[0]["link"],
        )

    if debug_gold18:
        print(
            "Navasan gold18 debug scan completed."
        )

    return posts
