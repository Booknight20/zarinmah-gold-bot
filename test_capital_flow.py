# -*- coding: utf-8 -*-

from capital_flow import (
    _latest_rahavard_report,
    _parse_amount,
    _format_billion,
    build_capital_flow_section,
)


def main():
    print("=" * 45)
    print("آزمایش دریافت اطلاعات جریان پول زرین ماه")
    print("=" * 45)

    print("\n1- آزمایش تبدیل اعداد:")
    print("مقدار ۲۵۰۰ میلیارد:")
    print(_format_billion(_parse_amount("2500 میلیارد")))

    print("\n2- دریافت گزارش ره‌آورد ۳۶۵:")

    try:
        report = _latest_rahavard_report()

        if report:
            print("گزارش دریافت شد.")
            print("-" * 30)
            print(report)
        else:
            print("گزارش خالی است.")

    except Exception as exc:
        print("دریافت گزارش ناموفق بود.")
        print(type(exc).__name__, str(exc))

    print("\n3- ساخت گزارش جریان نقدینگی:")

    try:
        section = build_capital_flow_section()
        print(section)
    except Exception as exc:
        print("ساخت گزارش ناموفق بود.")
        print(type(exc).__name__, str(exc))

    print("\nآزمایش تمام شد؛ هیچ پیامی ارسال نشده است.")


if __name__ == "__main__":
    main()
