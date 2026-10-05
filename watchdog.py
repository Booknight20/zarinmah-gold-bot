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
        "per_page": 50,
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
    """
    بررسی می‌کند آیا اجرای schedule مربوط به ساعت موردنظر
    در GitHub Actions وجود دارد یا نه.
    """

    # scheduled_time به وقت تهران است.
    # GitHub زمان را UTC برمی‌گرداند.
    scheduled_utc = scheduled_time.astimezone(ZoneInfo("UTC"))

    # کمی قبل از زمان موردنظر را هم پوشش می‌دهیم.
    search_from = scheduled_utc - timedelta(minutes=5)

    runs = get_workflow_runs(
        workflow_file,
        search_from,
    )

    matching_runs = []

    for run in runs:
        created_at = run.get("created_at")

        if not created_at:
            continue

        created_dt = datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        )

        # اجرای موردنظر باید تقریباً حوالی زمان schedule باشد.
        if created_dt >= search_from:
            matching_runs.append(run)

    if not matching_runs:
        print(
            "No scheduled GitHub Actions run found "
            "for the target period."
        )
        return "missing"

    matching_runs.sort(
        key=lambda run: run.get("created_at", ""),
        reverse=True,
    )

    run = matching_runs[0]

    status = run.get("status")
    conclusion = run.get("conclusion")

    print("Latest scheduled workflow:", run.get("id"))
    print("Workflow created:", run.get("created_at"))
    print("Workflow status:", status)
    print("Workflow conclusion:", conclusion)

    if status != "completed":
        return "running"

    if conclusion == "success":
        return "success"

    return "failed"


def run_script(script_name, retry_type):
    print(
        f"Running {script_name} "
        f"as {retry_type} watchdog retry..."
    )

    env = os.environ.copy()

    env["WATCHDOG_RETRY"] = "true"

    # بسیار مهم:
    # اگر این متغیر باقی بماند bot.py تصور می‌کند اجرای اصلی schedule است.
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
    Watchdog هر ۱۰ دقیقه اجرا می‌شود.

    همیشه ساعت قبل را بررسی می‌کنیم.

    مثال:
        19:40 -> بررسی ارسال ساعت 19
        19:50 -> بررسی ارسال ساعت 19
        20:00 -> بررسی ارسال ساعت 19
        20:10 -> بررسی ارسال ساعت 20

    بنابراین اگر اجرای ساعت 19 انجام نشده باشد،
    Watchdog آن را جبران می‌کند.
    """

    # اگر قبل از ساعت 00:10 هستیم، ساعت قبلی مربوط به روز قبل است.
    target_time = now.replace(
        second=0,
        microsecond=0,
    ) - timedelta(
        hours=1
    )

    scheduled_slot = target_time.strftime(
        "%Y-%m-%d %H"
    )

    scheduled_time = target_time.replace(
        minute=17,
        second=0,
        microsecond=0,
    )

    print()
    print("Checking hourly price post...")
    print("Target slot:", scheduled_slot)
    print(
        "Expected scheduled time:",
        scheduled_time.strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        ),
    )

    hourly_status = status.get(
        "hourly",
        {},
    )

    sent_slot = hourly_status.get(
        "slot"
    )

    # اگر قبلاً ارسال شده، هیچ کاری نکن.
    if sent_slot == scheduled_slot:
        print(
            "Hourly post was already sent "
            f"for {scheduled_slot}."
        )
        print("No retry needed.")
        return

    watchdog_status = status.setdefault(
        "watchdog",
        {},
    )

    attempted_slot = watchdog_status.get(
        "hourly_retry_slot"
    )

    # جلوگیری از اجرای چندباره watchdog برای یک ساعت.
    if attempted_slot == scheduled_slot:
        print(
            "Hourly watchdog retry was already "
            f"attempted for {scheduled_slot}."
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

    # اگر workflow هنوز در حال اجراست،
    # اجازه بده خودش پیام را ارسال کند.
    if workflow_state == "running":
        print(
            "Hourly workflow is still running."
        )
        print(
            "No watchdog retry will be performed."
        )
        return

    # اگر workflow موفق بوده ولی send_status هنوز ثبت نشده،
    # برای احتیاط retry نمی‌کنیم چون ممکن است commit وضعیت
    # هنوز انجام نشده باشد.
    #
    # در حالت فعلی، اگر status موفق باشد اما send_status
    # ثبت نشده باشد، اجازه retry داده می‌شود.
    if workflow_state == "success":
        print(
            "Scheduled workflow completed successfully, "
            "but send_status does not confirm the post."
        )
        print(
            "Starting watchdog retry to guarantee delivery."
        )

    elif workflow_state == "failed":
        print(
            "Scheduled workflow failed."
        )
        print(
            "Starting watchdog retry..."
        )

    elif workflow_state == "missing":
        print(
            "Scheduled workflow was not found."
        )
        print(
            "Starting watchdog retry..."
        )

    # قبل از اجرای retry ثبت می‌کنیم تا اگر cron
    # دوباره خیلی سریع اجرا شد، دوباره ارسال نکند.
    watchdog_status[
        "hourly_retry_slot"
    ] = scheduled_slot

    success = run_script(
        "bot.py",
        "Hourly",
    )

    if success:
        print(
            "Hourly watchdog retry finished successfully."
        )
    else:
        print(
            "Hourly watchdog retry FAILED."
        )


def check_daily(now, status):
    """
    تحلیل روزانه در 11:45 اجرا می‌شود.

    Watchdog حوالی 12:00 بررسی می‌کند.
    """

    if not (
        now.hour == 12
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

    print()
    print("Checking daily analysis...")
    print("Target date:", scheduled_date)

    daily_status = status.get(
        "daily",
        {},
    )

    sent_date = daily_status.get(
        "slot"
    )

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
            "Daily watchdog retry was already "
            "attempted for this date."
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

    print()
    print("Watchdog finished.")


if __name__ == "__main__":
    main()
