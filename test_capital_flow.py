# -*- coding: utf-8 -*-

import capital_flow

def main():
    print("=" * 45)
    print("بررسی فایل جریان پول زرین ماه")
    print("=" * 45)

    print("\nمسیر فایل بارگذاری‌شده:")
    print(capital_flow.__file__)

    print("\nتوابع موجود در capital_flow.py:")

    functions = [
        name
        for name in dir(capital_flow)
        if callable(getattr(capital_flow, name))
        and not name.startswith("__")
    ]

    for name in functions:
        print("-", name)

    required = [
        "_latest_rahavard_report",
        "_extract_flow_line",
        "_parse_amount",
        "_format_billion",
        "_flow_status",
        "build_capital_flow_section",
    ]

    print("\nبررسی توابع موردنیاز:")

    for name in required:
        if hasattr(capital_flow, name):
            print(f"OK: {name}")
        else:
            print(f"MISSING: {name}")

    print("\nپایان بررسی؛ هیچ پیامی ارسال نشده است.")


if __name__ == "__main__":
    main()
