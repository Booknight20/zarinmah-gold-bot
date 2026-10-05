import json
import os
import sys
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests


TEHRAN_TZ = ZoneInfo("Asia/Tehran")

REPO = os.environ.get(
    "GITHUB_REPOSITORY",
    "Booknight20/zarinmah-gold-bot",
)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

STATUS_FILE = "send_status.json"

HOURLY_WORKFLOW = "hourly.yml"


def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def load_send_status():
    if not os.path.exists(STATUS_FILE):
        print("send_status.json not found.")

        return {
            "hourly": {},
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
        data.setdefault("daily", {})
        data.setdefault("watchdog", {})

        return data

    except Exception as error:
        print("Could not load send status:", error)

        return {
            "hourly": {},
            "daily": {},
            "watchdog": {},
        }


def get_workflow_runs(workflow_file, created_after):
    url = (
        f"https://api.github.com/repos/{REPO}"
        f"/actions/workflows/{workflow_file}/runs"
    )

    params = {
        "per_page": 20,
        "event": "schedule",
    }

    response = requests.get(
        url,
        headers=github_headers(),
        params=params,
        timeout=30,
    )

    if response.status_code != 200:
        print("GitHub API error:", response.status_code)
        print(response.text)
        return []

    data = response.json()

    runs = []

    for run in data.get("workflow_runs", []):
        created_at = run.get("created_at")

        if not created_at:
            continue

        created_dt = datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        )

        if created_dt >= created_after:
            runs.append(run)

    return runs


def workflow_status(workflow_file, scheduled_time):
    runs = get_workflow_runs(
        workflow_file,
        scheduled_time - timedelta(minutes=5),
    )

    if not runs:
        return "missing"

    runs.sort(
        key=lambda run: run.get("created_at", ""),
        reverse=True,
    )

    run = runs[0]

    status = run.get("status")
    conclusion = run.get("conclusion")

    print("Latest workflow:", run.get("id"))
    print("Workflow status:", status)
    print("Workflow conclusion:", conclusion)

    if status != "completed":
        return "running"

    if conclusion == "success":
        return "success"

    return "failed"


def run_script(script_name, retry_type):
    print(
        f"Running {script_name} as {retry_type} watchdog retry..."
    )

    env = os.environ.copy()

    env["WATCHDOG_RETRY"] = "true"

    env.pop(
        "SCHEDULED_RUN",
        None,
    )

    result = subprocess.run(
        [
            sys.executable,
            script_name,
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    print("STDOUT:")
    print(result.stdout)

    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    if result.returncode != 0:
        print(
            f"{script_name} failed with exit code "
            f"{result.returncode}"
        )

        return False

    print(
        f"{retry_type} retry completed successfully."
    )

    return True


def check_hourly(now, status):
    """
    با cron هر ۱۰ دقیقه:
    قیمت ساعت 17 دقیقه بعد از گذشت حداقل 10 دقیقه بررسی می‌شود.

    اولین اجرای مناسب بعد از 17 دقیقه، ساعت XX:30 است.
    """

    if not (
        now.minute >= 27
        and now.minute <= 36
    ):
        return

    scheduled_slot = now.strftime(
        "%Y-%m-%d %H"
    )

    scheduled_time = now.replace(
        minute=17,
        second=0,
        microsecond=0,
    )

    print("Checking hourly price post...")
    print("Target slot:", scheduled_slot)

    hourly_status = status.get(
        "hourly",
        {},
    )

    sent_slot = hourly_status.get("slot")

    if sent_slot == scheduled_slot:
        print("Hourly post was already sent.")
        print("No retry needed.")
        return

    watchdog_status = status.setdefault(
        "watchdog",
        {},
    )

    attempted_slot = watchdog_status.get(
        "hourly_retry_slot"
    )

    if attempted_slot == scheduled_slot:
        print(
            "Hourly watchdog retry was already attempted."
        )
        print("No second retry will be performed.")
        return

    workflow_state = workflow_status(
        HOURLY_WORKFLOW,
        scheduled_time,
    )

    print(
        "Hourly workflow state:",
        workflow_state,
    )

    if workflow_state == "running":
        print(
            "Hourly workflow is still running."
        )
        print("No retry will be performed.")
        return

    print(
        "Hourly post was not confirmed."
    )

    print(
        "Starting hourly watchdog retry..."
    )

    watchdog_status[
        "hourly_retry_slot"
    ] = scheduled_slot

    run_script(
        "bot.py",
        "Hourly",
    )


def check_daily(now, status):
    """
    تحلیل روزانه در 11:45 اجرا می‌شود.

    چون cron هر 10 دقیقه است،
    Watchdog در 12:00 آن را بررسی می‌کند.
    """

    if not (
        now.hour == 12
        and now.minute <= 9
    ):
        return

    scheduled_date = now.strftime(
        "%Y-%m-%d"
    )

    scheduled_time = now.replace(
        hour=11,
        minute=45,
        second=0,
        microsecond=0,
    )

    print("Checking daily analysis...")
    print("Target date:", scheduled_date)

    daily_status = status.get(
        "daily",
        {},
    )

    sent_date = daily_status.get("slot")

    if sent_date == scheduled_date:
        print(
            "Daily analysis was already sent."
        )
        print("No retry needed.")
        return

    watchdog_status = status.setdefault(
        "watchdog",
        {},
    )

    attempted_date = watchdog_status.get(
        "daily_retry_date"
    )

    if attempted_date == scheduled_date:
        print(
            "Daily watchdog retry was already attempted."
        )
        print("No second retry will be performed.")
        return

    workflow_state = workflow_status(
        HOURLY_WORKFLOW,
        scheduled_time,
    )

    print(
        "Daily workflow state:",
        workflow_state,
    )

    if workflow_state == "running":
        print(
            "Daily workflow is still running."
        )
        print("No retry will be performed.")
        return

    print(
        "Daily analysis was not confirmed."
    )

    print(
        "Starting daily watchdog retry..."
    )

    watchdog_status[
        "daily_retry_date"
    ] = scheduled_date

    run_script(
        "daily_analysis.py",
        "Daily",
    )


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

    print("Current send status:")

    print(
        json.dumps(
            status,
            ensure_ascii=False,
            indent=2,
        )
    )

    check_hourly(
        now,
        status,
    )

    check_daily(
        now,
        status,
    )

    print("Watchdog finished.")


if __name__ == "__main__":
    main()
