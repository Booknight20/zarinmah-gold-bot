import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests


TEHRAN_TZ = ZoneInfo("Asia/Tehran")

REPO = os.environ.get(
    "GITHUB_REPOSITORY",
    "Booknight20/zarinmah-gold-bot",
)

GITHUB_TOKEN = os.environ.get(
    "GITHUB_TOKEN"
)

STATUS_FILE = "send_status.json"

HOURLY_WORKFLOW = "hourly.yml"
DAILY_WORKFLOW = "daily-analysis.yml"
NEWS_WORKFLOW = "news-collector.yml"

API_BASE = "https://api.github.com"


# =========================================================
# GitHub API
# =========================================================

def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def load_send_status():
    if not os.path.exists(STATUS_FILE):
        return {
            "hourly": {},
            "telegram_hourly": {},
            "eitaa_hourly": {},
            "daily": {},
            "watchdog": {},
        }

    try:
        with open(
            STATUS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            data = {}

        data.setdefault("hourly", {})
        data.setdefault("telegram_hourly", {})
        data.setdefault("eitaa_hourly", {})
        data.setdefault("daily", {})
        data.setdefault("watchdog", {})

        return data

    except Exception as error:
        print(
            "Could not load send status:",
            repr(error),
        )

        return {
            "hourly": {},
            "telegram_hourly": {},
            "eitaa_hourly": {},
            "daily": {},
            "watchdog": {},
        }


def get_workflow_runs(
    workflow_file,
    event=None,
):
    url = (
        f"{API_BASE}/repos/{REPO}"
        f"/actions/workflows/{workflow_file}/runs"
    )

    params = {
        "per_page": 50,
    }

    if event:
        params["event"] = event

    try:
        response = requests.get(
            url,
            headers=github_headers(),
            params=params,
            timeout=30,
        )
    except requests.RequestException as error:
        print(
            f"GitHub API request failed "
            f"for {workflow_file}:",
            repr(error),
        )
        return []

    print(
        f"GitHub API status for {workflow_file}:",
        response.status_code,
    )

    if response.status_code != 200:
        print(response.text)
        return []

    try:
        return response.json().get(
            "workflow_runs",
            [],
        )
    except ValueError:
        return []


def workflow_state_in_window(
    workflow_file,
    target_time,
):
    runs = get_workflow_runs(
        workflow_file
    )

    window_start = (
        target_time
        - timedelta(minutes=5)
    )

    now = datetime.now(
        TEHRAN_TZ
    )

    window_end = now

    matching_runs = []

    for run in runs:
        created_at = run.get(
            "created_at"
        )

        if not created_at:
            continue

        try:
            created_dt = datetime.fromisoformat(
                created_at.replace(
                    "Z",
                    "+00:00",
                )
            )
        except Exception:
            continue

        if (
            window_start
            <= created_dt
            <= window_end
        ):
            matching_runs.append(
                run
            )

    if not matching_runs:
        return "missing"

    matching_runs.sort(
        key=lambda run: run.get(
            "created_at",
            "",
        ),
        reverse=True,
    )

    run = matching_runs[0]

    print()
    print(
        "Found workflow run:"
    )
    print(
        "Workflow:",
        workflow_file,
    )
    print(
        "Run ID:",
        run.get("id"),
    )
    print(
        "Event:",
        run.get("event"),
    )
    print(
        "Created:",
        run.get("created_at"),
    )
    print(
        "Status:",
        run.get("status"),
    )
    print(
        "Conclusion:",
        run.get("conclusion"),
    )

    if run.get(
        "status"
    ) != "completed":
        return "running"

    if run.get(
        "conclusion"
    ) == "success":
        return "success"

    return "failed"


def workflow_state_for_manual_or_schedule(
    workflow_file,
    target_time,
):
    runs = get_workflow_runs(
        workflow_file
    )

    window_start = (
        target_time
        - timedelta(minutes=5)
    )

    now = datetime.now(
        TEHRAN_TZ
    )

    matching_runs = []

    for run in runs:
        created_at = run.get(
            "created_at"
        )

        if not created_at:
            continue

        try:
            created_dt = datetime.fromisoformat(
                created_at.replace(
                    "Z",
                    "+00:00",
                )
            )
        except Exception:
            continue

        if (
            window_start
            <= created_dt
            <= now
        ):
            matching_runs.append(
                run
            )

    if not matching_runs:
        return "missing"

    matching_runs.sort(
        key=lambda run: run.get(
            "created_at",
            "",
        ),
        reverse=True,
    )

    run = matching_runs[0]

    print()
    print(
        "Found latest daily workflow:"
    )
    print(
        "Run ID:",
        run.get("id"),
    )
    print(
        "Event:",
        run.get("event"),
    )
    print(
        "Created:",
        run.get("created_at"),
    )
    print(
        "Status:",
        run.get("status"),
    )
    print(
        "Conclusion:",
        run.get("conclusion"),
    )

    if run.get(
        "status"
    ) != "completed":
        return "running"

    if run.get(
        "conclusion"
    ) == "success":
        return "success"

    return "failed"


# =========================================================
# Trigger workflow
# =========================================================

def trigger_workflow(
    workflow_file
):
    url = (
        f"{API_BASE}/repos/{REPO}"
        f"/actions/workflows/{workflow_file}"
        f"/dispatches"
    )

    payload = {
        "ref": "main",
    }

    print()
    print(
        "Triggering GitHub workflow..."
    )
    print(
        "Workflow:",
        workflow_file,
    )
    print(
        "Repository:",
        REPO,
    )

    try:
        response = requests.post(
            url,
            headers=github_headers(),
            json=payload,
            timeout=30,
        )
    except requests.RequestException as error:
        print(
            "GitHub trigger request failed:",
            repr(error),
        )
        return False

    print(
        "GitHub trigger response:",
        response.status_code,
    )

    if response.status_code == 204:
        print(
            "GitHub workflow triggered successfully."
        )
        return True

    print(
        "GitHub trigger failed."
    )
    print(
        response.text
    )

    return False


# =========================================================
# بررسی قیمت ساعتی
# =========================================================

def check_hourly(
    now,
    status,
):
    # -----------------------------------------
    # خاموشی شبانه
    # -----------------------------------------

    if (
        now.hour >= 22
        or now.hour < 9
    ):
        print()
        print(
            "Hourly price publishing is disabled "
            "between 22:00 and 08:59 Tehran time."
        )
        print(
            "Watchdog will NOT trigger hourly retry."
        )
        return

    # -----------------------------------------
    # صبح
    # -----------------------------------------

    if (
        now.hour == 9
        and now.minute < 27
    ):
        print()
        print(
            "Morning price window has started."
        )
        print(
            "Waiting for the 09:17 scheduled run."
        )
        return

    # -----------------------------------------
    # تعیین ساعت مورد انتظار
    # -----------------------------------------

    if now.minute >= 27:

        target_time = now.replace(
            minute=17,
            second=0,
            microsecond=0,
        )

    else:

        previous_hour = (
            now
            - timedelta(hours=1)
        )

        target_time = previous_hour.replace(
            minute=17,
            second=0,
            microsecond=0,
        )

    scheduled_slot = (
        target_time.strftime(
            "%Y-%m-%d %H"
        )
    )

    print()
    print(
        "==================================="
    )
    print(
        "Checking hourly price delivery..."
    )
    print(
        "Target slot:",
        scheduled_slot,
    )
    print(
        "Expected scheduled time:",
        target_time.strftime(
            "%Y-%m-%d %H:%M:%S %z"
        ),
    )

    # -----------------------------------------
    # وضعیت هر مقصد
    # -----------------------------------------

    telegram_sent = (
        status.get(
            "telegram_hourly",
            {},
        ).get(
            "slot"
        )
        == scheduled_slot
    )

    eitaa_sent = (
        status.get(
            "eitaa_hourly",
            {},
        ).get(
            "slot"
        )
        == scheduled_slot
    )

    hourly_complete = (
        status.get(
            "hourly",
            {},
        ).get(
            "slot"
        )
        == scheduled_slot
    )

    print(
        "Telegram status:",
        "SENT"
        if telegram_sent
        else "NOT SENT",
    )

    print(
        "Eitaa status:",
        "SENT"
        if eitaa_sent
        else "NOT SENT",
    )

    print(
        "Hourly complete:",
        "YES"
        if hourly_complete
        else "NO",
    )

    # -----------------------------------------
    # اگر هر دو واقعاً ثبت شده‌اند
    # -----------------------------------------

    if (
        telegram_sent
        and eitaa_sent
        and hourly_complete
    ):
        print(
            "Telegram + Eitaa were both "
            "successfully recorded."
        )
        print(
            "No hourly retry needed."
        )
        return

    # -----------------------------------------
    # بررسی Workflow
    # -----------------------------------------

    workflow_state = (
        workflow_state_in_window(
            HOURLY_WORKFLOW,
            target_time,
        )
    )

    print(
        "Hourly workflow state:",
        workflow_state,
    )

    if workflow_state == "running":
        print(
            "Hourly workflow is still running."
        )
        return

    # -----------------------------------------
    # اگر Workflow موفق شده ولی یکی از مقصدها
    # ثبت نشده، دوباره اجرا می‌کنیم.
    #
    # bot.py خودش تشخیص می‌دهد کدام مقصد
    # قبلاً ارسال شده و کدام مقصد باقی مانده.
    # -----------------------------------------

    if workflow_state == "success":

        if telegram_sent and not eitaa_sent:
            print(
                "Telegram is already recorded."
            )
            print(
                "Eitaa is NOT recorded."
            )
            print(
                "Retrying hourly workflow so "
                "only the missing destination "
                "can be completed."
            )

        elif eitaa_sent and not telegram_sent:
            print(
                "Eitaa is already recorded."
            )
            print(
                "Telegram is NOT recorded."
            )
            print(
                "Retrying hourly workflow so "
                "only the missing destination "
                "can be completed."
            )

        else:
            print(
                "Workflow succeeded but the "
                "hourly completion state is incomplete."
            )
            print(
                "Retrying hourly workflow."
            )

    # -----------------------------------------
    # اگر Workflow شکست خورده یا پیدا نشده
    # -----------------------------------------

    elif workflow_state == "failed":
        print(
            "Hourly workflow failed."
        )
        print(
            "Retrying hourly workflow."
        )

    elif workflow_state == "missing":
        print(
            "Hourly workflow was not confirmed."
        )
        print(
            "Retrying hourly workflow."
        )

    # -----------------------------------------
    # اجرای مجدد
    # -----------------------------------------

    success = trigger_workflow(
        HOURLY_WORKFLOW
    )

    if success:
        print(
            "Hourly retry triggered successfully."
        )
    else:
        print(
            "Hourly retry could not be triggered."
        )


# =========================================================
# بررسی تحلیل روزانه
# =========================================================

def check_daily(
    now,
    status,
):
    if not (
        now.hour == 12
        and now.minute <= 29
    ):
        return

    target_time = now.replace(
        hour=11,
        minute=45,
        second=0,
        microsecond=0,
    )

    today = now.strftime(
        "%Y-%m-%d"
    )

    print()
    print(
        "==================================="
    )
    print(
        "Checking daily market analysis..."
    )
    print(
        "Target date:",
        today,
    )

    daily_status = (
        status.get(
            "daily",
            {},
        )
    )

    sent_date = daily_status.get(
        "slot"
    )

    if sent_date == today:
        print(
            "Daily analysis was already recorded."
        )
        print(
            "No retry needed."
        )
        return

    workflow_state = (
        workflow_state_for_manual_or_schedule(
            DAILY_WORKFLOW,
            target_time,
        )
    )

    print(
        "Daily workflow state:",
        workflow_state,
    )

    if workflow_state == "running":
        print(
            "Daily workflow is still running."
        )
        return

    if workflow_state == "success":
        print(
            "Daily workflow completed successfully."
        )
        return

    print(
        "Daily workflow was not confirmed."
    )

    success = trigger_workflow(
        DAILY_WORKFLOW
    )

    if success:
        print(
            "Daily analysis retry triggered."
        )
    else:
        print(
            "Daily analysis retry failed."
        )


# =========================================================
# اخبار
# =========================================================

def get_latest_news_slot(
    now,
):
    if now.minute < 5:
        previous_hour = (
            now
            - timedelta(hours=1)
        )

        return previous_hour.replace(
            minute=30,
            second=0,
            microsecond=0,
        )

    if now.minute < 35:
        return now.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

    return now.replace(
        minute=30,
        second=0,
        microsecond=0,
    )


def check_news(
    now,
    status,
):
    target_time = get_latest_news_slot(
        now
    )

    elapsed = (
        now
        - target_time
    )

    if elapsed < timedelta(
        minutes=5
    ):
        print()
        print(
            "News workflow is still "
            "within the startup grace period."
        )
        return

    scheduled_slot = (
        target_time.strftime(
            "%Y-%m-%d %H:%M"
        )
    )

    print()
    print(
        "==================================="
    )
    print(
        "Checking news workflow..."
    )
    print(
        "News target slot:",
        scheduled_slot,
    )

    workflow_state = (
        workflow_state_in_window(
            NEWS_WORKFLOW,
            target_time,
        )
    )

    print(
        "News workflow state:",
        workflow_state,
    )

    if workflow_state == "success":
        print(
            "News workflow completed successfully."
        )
        return

    if workflow_state == "running":
        print(
            "News workflow is still running."
        )
        return

    print(
        "News workflow was not confirmed."
    )

    success = trigger_workflow(
        NEWS_WORKFLOW
    )

    if success:
        print(
            "News workflow retry triggered."
        )
    else:
        print(
            "News workflow retry failed."
        )


# =========================================================
# main
# =========================================================

def main():

    if not GITHUB_TOKEN:
        print(
            "ERROR: GITHUB_TOKEN is missing."
        )
        sys.exit(1)

    now = datetime.now(
        TEHRAN_TZ
    )

    print(
        "==================================="
    )

    print(
        "ZarinMah Watchdog"
    )

    print(
        "Tehran time:",
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    print(
        "==================================="
    )

    status = load_send_status()

    # -----------------------------------------
    # 1. قیمت ساعتی
    # -----------------------------------------

    check_hourly(
        now,
        status,
    )

    # -----------------------------------------
    # 2. تحلیل روزانه
    # -----------------------------------------

    check_daily(
        now,
        status,
    )

    # -----------------------------------------
    # 3. اخبار
    # -----------------------------------------

    check_news(
        now,
        status,
    )

    print()
    print(
        "==================================="
    )

    print(
        "Watchdog finished."
    )

    print(
        "===================================",
    )


if __name__ == "__main__":
    main()
