import os
import sys
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests


# ==============================
# تنظیمات
# ==============================

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

REPO = os.environ.get("GITHUB_REPOSITORY", "Booknight20/zarinmah-gold-bot")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

HOURLY_WORKFLOW = "hourly.yml"
DAILY_WORKFLOW = "daily-analysis.yml"


# ==============================
# ابزارهای کمکی
# ==============================

def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_workflow_runs(workflow_file, created_after):
    """
    آخرین اجرای Workflow را بعد از زمان مشخص پیدا می‌کند.
    """

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


def workflow_already_handled(workflow_file, scheduled_time):
    """
    بررسی می‌کند آیا Workflow مربوط به زمان موردنظر
    اجرا شده و با موفقیت تمام شده است یا هنوز در حال اجراست.
    """

    runs = get_workflow_runs(
        workflow_file,
        scheduled_time - timedelta(minutes=5),
    )

    if not runs:
        return False

    for run in runs:
        status = run.get("status")
        conclusion = run.get("conclusion")

        if status != "completed":
            print("Workflow is still running:", run.get("id"))
            return True

        if conclusion == "success":
            print("Successful workflow found:", run.get("id"))
            return True

    return False


def run_script(script_name):
    """
    اجرای ربات اصلی.
    """

    print(f"Running {script_name} ...")

    result = subprocess.run(
        [sys.executable, script_name],
        capture_output=True,
        text=True,
    )

    print("STDOUT:")
    print(result.stdout)

    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f"{script_name} failed with exit code {result.returncode}"
        )

    print(f"{script_name} completed successfully.")


# ==============================
# منطق اصلی Watchdog
# ==============================

def main():

    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN is missing.")
        sys.exit(1)

    now = datetime.now(TEHRAN_TZ)

    print("===================================")
    print("ZarinMah Watchdog")
    print("Tehran time:", now.strftime("%Y-%m-%d %H:%M:%S"))
    print("===================================")

    # --------------------------------
    # Retry پیام ساعتی
    # --------------------------------
    #
    # پیام اصلی ساعت XX:17 ارسال می‌شود.
    # Watchdog ده دقیقه بعد، یعنی XX:27 بررسی می‌کند.
    #

    if now.minute == 27:

        scheduled_time = now.replace(
            minute=17,
            second=0,
            microsecond=0,
        )

        print("Checking hourly price post...")

        already_handled = workflow_already_handled(
            HOURLY_WORKFLOW,
            scheduled_time,
        )

        if already_handled:
            print("Hourly workflow already handled. No retry needed.")

        else:
            print("Hourly workflow was not successfully handled.")
            print("Retrying hourly bot...")

            run_script("bot.py")

    # --------------------------------
    # Retry تحلیل روزانه
    # --------------------------------
    #
    # تحلیل اصلی ساعت 11:45 ارسال می‌شود.
    # Watchdog ساعت 11:55 بررسی می‌کند.
    #

    if now.hour == 11 and now.minute == 55:

        scheduled_time = now.replace(
            minute=45,
            second=0,
            microsecond=0,
        )

        print("Checking daily analysis...")

        already_handled = workflow_already_handled(
            DAILY_WORKFLOW,
            scheduled_time,
        )

        if already_handled:
            print("Daily workflow already handled. No retry needed.")

        else:
            print("Daily workflow was not successfully handled.")
            print("Retrying daily analysis...")

            run_script("daily_analysis.py")

    print("Watchdog finished.")


if __name__ == "__main__":
    main()
