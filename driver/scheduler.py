"""Legacy scheduler.

DEPRECATED: the scheduling is now done by the web service in
``web/scheduler.py``.  This script must not run at the same time as the
``humidifier-web`` service because both would control the GPIO pins.
"""

import time
import os
from datetime import datetime, timedelta
from humidifier import HumidifierDriver

LOG_FILE = "log.txt"
LOG_RETENTION_DAYS = 7


def clean_log() -> None:
    if not os.path.exists(LOG_FILE):
        return
    cutoff = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()
    with open(LOG_FILE, "w") as f:
        for line in lines:
            try:
                log_time_str = line.split("]")[0][1:]
                log_time = datetime.strptime(log_time_str, "%Y-%m-%d %H:%M:%S")
                if log_time >= cutoff:
                    f.write(line)
            except (ValueError, IndexError):
                f.write(line)


def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def wait_until_next_hour() -> None:
    now = datetime.now()
    next_hour = (now.replace(minute=0, second=0, microsecond=0)
                 .replace(hour=now.hour + 1))
    wait_seconds = (next_hour - now).total_seconds()
    log(f"Waiting {wait_seconds:.0f}s until {next_hour.strftime('%H:%M')}")
    time.sleep(wait_seconds)


def main() -> None:
    clean_log()
    last_clean = datetime.now()
    log("Scheduler started. Running at every full hour for 15 minutes.")
    while True:
        try:
            with HumidifierDriver(force_cleanup=True) as h:
                while True:
                    wait_until_next_hour()

                    log("Turning ON - highest stage")
                    h.set_stage_auto(1)

                    time.sleep(10 * 60)

                    log("Turning OFF")
                    h.set_off()

                    if datetime.now() - last_clean >= timedelta(days=1):
                        clean_log()
                        last_clean = datetime.now()
        except Exception as e:
            log(f"ERROR: {e}. Restarting in 10s...")
            time.sleep(10)


if __name__ == "__main__":
    main()