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


def get_workflow_runs(workflow_file, scheduled_time):
    url = (
        f"https://api.github.com/repos/{REPO}"
        f"/actions/workflows/{workflow_file}/runs"
    )

    response = requests.get(
        url,
        headers=github_headers(),
        params={
            "per_page": 50,
            "event": "schedule",
        },
        timeout=30,
    )

    if response.status_code != 200:
        print(
            "GitHub API error while reading workflow runs:",
            response.status_code,
        )
        print(response.text)
        return []

    data = response.json()

    runs = []

    # اجازه می‌دهیم اجرای GitHub کمی زودتر یا دیرتر از cron ثبت شود.
    window_start = scheduled_time - timedelta(minutes=5)
    window_end = scheduled_time + timedelta(minutes=25)

    for run in data.get("workflow_runs", []):
        created_at = run.get("created_at")

        if not created_at:
            continue

        try:
            created_dt = datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            )
        except Exception:
            continue

        if window_start <= created_dt <= window_end:
            runs.append(run)

    return runs


def workflow_status(workflow_file, scheduled_time):
    runs = get_workflow_runs(
        workflow_file,
        scheduled_time,
    )

    if not runs:
        return "missing"

    runs.sort(
        key=lambda run: run.get("created_at", ""),
        reverse=True,
    )

    run = runs[0]

    print("Found scheduled workflow run:")
    print("Run ID:", run.get("id"))
    print("Run created:", run.get("created_at"))
    print("Run status:", run.get("status"))
    print("Run conclusion:", run.get("conclusion"))

    status = run.get("status")
    conclusion = run.get("conclusion")

    if status != "completed":
        return "running"

    if conclusion == "success":
        return "success"

    return "failed"


def trigger_workflow(workflow_file):
    url = (
        f"https://api.github.com/repos/{REPO}"
        f"/actions/workflows/{workflow_file}/dispatches"
    )

    payload = {
        "ref": "main"
    }

    print("Triggering GitHub workflow...")
    print("Workflow:", workflow_file)
    print("Repository:", REPO)

    response = requests.post(
        url,
        headers=github_headers(),
        json=payload,
        timeout=30,
    )

    print(
        "GitHub trigger response:",
        response.status_code,
    )

    if response.status_code == 204:
        print("GitHub workflow triggered successfully.")
        return True

    print("GitHub trigger failed.")
    print(response.text)

    return False


def check_hourly(now, status):
    """
    Scheduled hourly workflow:
    every hour at minute 17.

    Watchdog runs every 10 minutes.

    Before minute 27:
        check the previous hour.

    From minute 27 onward:
        check the current hour.

    Example:
        19:20 -> check 18:17
        19:30 -> check 19:17
        19:40 -> check 19:17
        19:50 -> check 19:17
    """

    if now.minute >= 27:
        target_time = now.replace(
            minute=17,
            second=0,
            microsecond=0,
        )
    else:
        previous_hour = now - timedelta(hours=1)

        target_time = previous_hour.replace(
            minute=17,
            second=0,
            microsecond=0,
        )

    scheduled_slot = target_time.strftime(
        "%Y-%m-%d %H"
    )

    print()
    print("Checking hourly price post...")
    print("Target slot:", scheduled_slot)
    print(
        "Expected scheduled time:",
        target_time.strftime("%Y-%m-%d %H:%M:%S %z"),
    )

    hourly_status = status.get(
        "hourly",
        {},
    )

    sent_slot = hourly_status.get("slot")

    if sent_slot == scheduled_slot:
        print(
            "Hourly post was already sent according to send_status.json."
        )
        print("No retry needed.")
        return

    watchdog_status = status.setdefault(
        "watchdog",
        {},
    )

    attempted_slot = watchdog_status.get(
        "hourly_trigger_slot"
    )

    if attempted_slot == scheduled_slot:
        print(
            "Watchdog already triggered this slot."
        )
        print("No second trigger will be performed.")
        return

    workflow_state = workflow_status(
        HOURLY_WORKFLOW,
        target_time,
    )

    print(
        "Hourly workflow state:",
        workflow_state,
    )

    if workflow_state == "success":
        print(
            "Scheduled GitHub Actions run completed successfully."
        )
        print(
            "No retry will be performed."
        )
        return

    if workflow_state == "running":
        print(
            "Scheduled GitHub Actions run is still running."
        )
        print(
            "No retry will be performed."
        )
        return

    if workflow_state == "failed":
        print(
            "Scheduled GitHub Actions run failed."
        )
    else:
        print(
            "No scheduled GitHub Actions run found for the target period."
        )

    print(
        "Starting GitHub workflow retry..."
    )

    success = trigger_workflow(
        HOURLY_WORKFLOW
    )

    if success:
        watchdog_status[
            "hourly_trigger_slot"
        ] = scheduled_slot

        print(
            "Hourly GitHub retry triggered successfully."
        )
    else:
        print(
            "Hourly GitHub retry could not be triggered."
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

    print()
    print("Watchdog finished.")


if __name__ == "__main__":
    main()
