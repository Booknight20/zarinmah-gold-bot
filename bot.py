def extract_dollar(text, unit):
    text = normalize_for_search(text)

    patterns = [
        # TGJU:
        # قیمت لحظه ای : 2,692,000 ریال
        r"(?:قیمت\s*)?دلار"
        r".{0,250}?"
        r"قیمت\s*لحظه\s*ای"
        r"\s*[:：]?\s*"
        r"([\d,]+)"
        r"\s*ریال",

        # TGJU:
        # قیمت دلار : 2,692,000 ریال
        r"(?:قیمت\s*)?دلار"
        r".{0,150}?"
        r"[:：]\s*"
        r"([\d,]+)"
        r"\s*ریال",

        # مثقال / نوسان:
        # دلار آمریکا فروش : 269,200 تومان
        r"دلار\s*آمریکا\s*فروش"
        r".{0,120}?"
        r"[:：]\s*"
        r"([\d,]+)"
        r"\s*تومان",

        # حالت عمومی
        r"دلار"
        r".{0,100}?"
        r"([\d,]+)"
        r"\s*تومان",
    ]

    candidates = []

    for pattern in patterns:

        matches = re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        for match in matches:

            number_text = match.group(1)

            suffix = text[
                match.end():
                match.end() + 20
            ]

            detected_unit = unit

            if "ریال" in suffix:
                detected_unit = "rial"

            elif "تومان" in suffix:
                detected_unit = "toman"

            price = parse_number(
                number_text,
                detected_unit,
            )

            if not price:
                continue

            # ------------------------------------------------
            # کنترل منطقی قیمت دلار
            # عدد 1، 10، 100 و اعداد غیرواقعی حذف شوند.
            # ------------------------------------------------

            if price < 10000:
                continue

            if price > 10000000:
                continue

            candidates.append(price)

    if not candidates:
        return None

    # نزدیک‌ترین مقدار به محدوده رایج بازار
    # را انتخاب می‌کنیم.
    candidates.sort()

    return candidates[0]
