
# -*- coding: utf-8 -*-

import traceback

from capital_flow import (
    _latest_rahavard_report,
    _extract_flow_line,
    _parse_amount,
    _format_billion,
    _flow_status,
)


def main():
    print("=" * 45)
    print("آزمایش جریان پول زرین ماه")
    print("=" * 45)

    print("\nآزمون تبدیل واحدها:")
    examples = [
        "۲۵۰ میلیارد تومان",
        "۱.۵ همت",
        "۵۰۰ میلیون تومان",
        "۲۵۵- میلیارد تومان",
    ]

    for item in examples:
        result = _parse_amount(item)
        print(f"{item} => {_format_billion(result)}")

    print("\nدریافت آخرین گزارش قابل تشخیص از ره‌آورد...")

    try:
        report = _latest_rahavard_report()

        if not report:
            print("خطا: متن گزارش خالی است.")
            return

        print("\nمتن گزارش دریافت‌شده:")
        print("-" * 45)
        print(report)
        print("-" * 45)

        categories = {
            "معاملات خرد": [r"معاملات\s*خرد"],
            "درآمد ثابت": [r"درآمد\s*ثابت"],
            "صندوق اهرمی": [r"صندوق\s*های?\s*اهرم"],
        }

        print("\nنتیجه استخراج آزمایشی:")

        for name, patterns in categories.items():
            value, source_line = _extract_flow_line(
                report,
                patterns,
            )

            print(f"\n{name}:")

            if value is None:
                print("رقم قابل استخراج نیست.")
            else:
                print("رقم:", _format_billion(value))
                print("برداشت اولیه:", _flow_status(value))
                print("خط منبع:", source_line)

        print("\nپایان آزمایش. هیچ پیامی ارسال نشده است.")

    except Exception as error:
        print("\nآزمایش با خطا روبه‌رو شد:")
        print(type(error).__name__, str(error))
        traceback.print_exc()


if __name__ == "__main__":
    main()
