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
DAILY_WORKFLOW = "daily-analysis.yml"


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
            "daily": {},
            "watchdog": {},
        }

    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as file:
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


def get_workflow_runs(workflow_file, event=None):
    url = (
        f"https://api.github.com/repos/{REPO}"
        f"/actions/workflows/{workflow_file}/runs"
    )

    params = {
        "per_page": 50,
    }

    if event:
        params["event"] = event

    response = requests.get(
        url,
        headers=github_headers(),
        params=params,
        timeout=30,
    )

    print(
        f"GitHub API status for {workflow_file}:",
        response.status_code,
    )

    if response.status_code != 200:
        print(response.text)
        return []

    return response.json().get(
        "workflow_runs",
        [],
    )


def get_scheduled_workflow_state(
    workflow_file,
    scheduled_time,
):
    runs = get_workflow_runs(
        workflow_file,
        event="schedule",
    )

    window_start = scheduled_time - timedelta(minutes=5)
    window_end = scheduled_time + timedelta(minutes=25)

    matching_runs = []

    for run in runs:
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
            matching_runs.append(run)

    if not matching_runs:
        return "missing"

    matching_runs.sort(
        key=lambda run: run.get("created_at", ""),
        reverse=True,
    )

    run = matching_runs[0]

    print("Found scheduled workflow:")
    print("Run ID:", run.get("id"))
    print("Created:", run.get("created_at"))
    print("Status:", run.get("status"))
    print("Conclusion:", run.get("conclusion"))

    if run.get("status") != "completed":
        return "running"

    if run.get("conclusion") == "success":
        return "success"

    return "failed"


def get_manual_workflow_state(
    workflow_file,
    target_date,
):
    runs = get_workflow_runs(
        workflow_file,
        event="workflow_dispatch",
    )

    matching_runs = []

    for run in runs:
        created_at = run.get("created_at")

        if not created_at:
            continue

        try:
            created_dt = datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            )
            created_tehran = created_dt.astimezone(
                TEHRAN_TZ
            )
        except Exception:
            continue

        if created_tehran.date() == target_date.date():
            matching_runs.append(run)

    if not matching_runs:
        return "missing"

    matching_runs.sort(
        key=lambda run: run.get("created_at", ""),
        reverse=True,
    )

    run = matching_runs[0]

    print("Found daily workflow:")
    print("Run ID:", run.get("id"))
    print("Created:", run.get("created_at"))
    print("Status:", run.get("status"))
    print("Conclusion:", run.get("conclusion"))

    if run.get("status") != "completed":
        return "running"

    if run.get("conclusion") == "success":
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

    print()
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
        print(
            "GitHub workflow triggered successfully."
        )
        return True

    print("GitHub trigger failed.")
    print(response.text)

    return False


def check_hourly(now, status):
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
        target_time.strftime(
            "%Y-%m-%d %H:%M:%S %z"
        ),
    )

    sent_slot = status.get(
        "hourly",
        {},
    ).get("slot")

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
            "Watchdog already triggered this hourly slot."
        )
        return

    workflow_state = get_scheduled_workflow_state(
        HOURLY_WORKFLOW,
        target_time,
    )

    print(
        "Hourly workflow state:",
        workflow_state,
    )

    if workflow_state == "success":
        print(
            "Scheduled hourly workflow completed successfully."
        )
        return

    if workflow_state == "running":
        print(
            "Scheduled hourly workflow is still running."
        )
        return

    print(
        "Scheduled hourly workflow was not confirmed."
    )

    success = trigger_workflow(
        HOURLY_WORKFLOW
    )

    if success:
        watchdog_status[
            "hourly_trigger_slot"
        ] = scheduled_slot

        print(
            "Hourly workflow retry triggered successfully."
        )


def check_daily(now, status):
    """
    Daily analysis should normally be completed
    after the daily analysis window.

    Watchdog checks it between 12:00 and 12:29 Tehran time.
    """

    if not (
        now.hour == 12
        and now.minute <= 29
    ):
        return

    target_date = now.replace(
        hour=11,
        minute=45,
        second=0,
        microsecond=0,
    )

    today = now.strftime(
        "%Y-%m-%d"
    )

    print()
    print("Checking daily market analysis...")
    print("Target date:", today)

    daily_status = status.get(
        "daily",
        {},
    )

    sent_date = daily_status.get("slot")

    if sent_date == today:
        print(
            "Daily analysis was already sent according to send_status.json."
        )
        print("No retry needed.")
        return

    watchdog_status = status.setdefault(
        "watchdog",
        {},
    )

    attempted_date = watchdog_status.get(
        "daily_trigger_date"
    )

    if attempted_date == today:
        print(
            "Watchdog already triggered daily analysis today."
        )
        return

    workflow_state = get_manual_workflow_state(
        DAILY_WORKFLOW,
        target_date,
    )

    print(
        "Daily workflow state:",
        workflow_state,
    )

    if workflow_state == "success":
        print(
            "Daily analysis workflow completed successfully."
        )
        return

    if workflow_state == "running":
        print(
            "Daily analysis workflow is still running."
        )
        return

    print(
        "Daily analysis workflow was not confirmed."
    )

    success = trigger_workflow(
        DAILY_WORKFLOW
    )

    if success:
        watchdog_status[
            "daily_trigger_date"
        ] = today

        print(
            "Daily analysis workflow triggered successfully."
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
    print("ZarinMah Watchdog")
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

    print()
    print("Watchdog finished.")


if __name__ == "__main__":
    main()
