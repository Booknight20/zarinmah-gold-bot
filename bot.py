        .get(
            "hourly",
            {},
        )
        .get(
            "slot"
        )
        == current_slot
    )

    if (
        (scheduled_run or watchdog_retry)
        and fully_sent
    ):

        print(
            f"Hourly post for "
            f"{current_slot} "
            "has already been sent "
            "to all destinations."
        )

        print(
            "Skipping duplicate message."
        )

        return

    # =====================================================
    # قیمت قبلی
    # =====================================================

    previous = (
        load_previous_prices()
    )

    # =====================================================
    # قیمت تازه TGJU؛ در نبود نرخ تازه، نوسان
    # =====================================================

    prices = get_hourly_prices_with_fallback()

    # =====================================================
    # ساخت پیام
    # =====================================================

    message = build_message(
        prices,
        previous,
    )

    # =====================================================
    # ارسال تلگرام
    # =====================================================

    if not telegram_sent:

        print(
            "Sending price message "
            "to Telegram..."
        )

        send_to_telegram(
            message
        )

        mark_telegram_sent(
            current_slot
        )

        telegram_sent = True

        print(
            "Telegram message sent successfully."
        )

    else:

        print(
            "Telegram message for "
            f"{current_slot} already sent."
        )

    # =====================================================
    # ارسال ایتا
    # =====================================================

    if not eitaa_sent:

        send_to_eitaa(
            message
        )

        mark_eitaa_sent(
            current_slot
        )

        eitaa_sent = True

    else:

        print(
            "Eitaa message for "
            f"{current_slot} already sent."
        )

    # =====================================================
    # هر دو مقصد موفق
    # =====================================================

    if (
        telegram_sent
        and eitaa_sent
    ):

        mark_hourly_complete(
            current_slot
        )

        print(
            "Telegram + Eitaa "
            "hourly send completed."
        )

    # =====================================================
    # ذخیره قیمت
    # =====================================================

    save_current_prices(
        prices
    )

    print(
        "Verified prices saved."
    )

    print(
        "Bot completed successfully."
    )


# =========================================================
# شروع
# =========================================================

if __name__ == "__main__":
    main()
