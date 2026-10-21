"""Local smoke test for the scheduling and persistence logic.

Run with:  python web/tests/smoke_test.py
The test uses the simulated humidifier so that no GPIO access is needed.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_store import Config, ConfigError, ConfigStore  # noqa: E402
from controller import HumidifierController  # noqa: E402
from scheduler import Scheduler  # noqa: E402
from schedule import (  # noqa: E402
    MODE_ANCHOR,
    MODE_HOUR,
    MODE_INTERVAL,
    next_anchor_occurrence,
    next_hour_occurrence,
    next_run_time,
    resolve_mode,
)

FAILURES = []


def check(condition, message):
    if condition:
        print(f"  ok   {message}")
    else:
        print(f"  FAIL {message}")
        FAILURES.append(message)


def test_config_persistence():
    print("config persistence")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.json")
        store = ConfigStore(path)
        config = store.load()
        check(config.run_duration_min == 15, "default duration is 15 minutes")
        check(config.interval_min == 60, "default interval is 60 minutes")

        store.update(run_duration_min=25, interval_min=120, stage=2)
        check(os.path.exists(path), "config file is written to disk")

        reloaded = ConfigStore(path).load()
        check(reloaded.run_duration_min == 25, "duration survives a restart")
        check(reloaded.interval_min == 120, "interval survives a restart")
        check(reloaded.stage == 2, "stage survives a restart")

        try:
            store.update(run_duration_min=0)
            check(False, "invalid duration is rejected")
        except ConfigError:
            check(True, "invalid duration is rejected")

        check(store.load().run_duration_min == 25, "a rejected value does not corrupt the config")
        store.update(last_run_at="2026-01-01T10:00:00")
        check(store.load().run_duration_min == 25, "the config is still writable afterwards")

        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{ this is broken")
        recovered = ConfigStore(path).load()
        check(recovered.run_duration_min == 25, "a broken config file falls back to the backup")


def test_schedule_modes():
    print("schedule modes")
    config = Config()
    config.schedule_mode = MODE_HOUR
    config.interval_min = 60
    check(resolve_mode(config) == MODE_HOUR, "an interval of 60 minutes runs on full hours")

    config.interval_min = 90
    check(
        resolve_mode(config) == MODE_INTERVAL,
        "an interval that is not a whole number of hours falls back to the interval",
    )

    config.schedule_mode = MODE_ANCHOR
    config.start_time = "06:30"
    config.interval_min = 90
    check(resolve_mode(config) == MODE_ANCHOR, "a start time is used for the fixed schedule")

    config.start_time = ""
    check(
        resolve_mode(config) == MODE_INTERVAL,
        "an empty start time falls back to a valid mode",
    )

    print("the next run on full hours")
    reference = datetime(2026, 10, 21, 19, 47, 12)
    check(
        next_hour_occurrence(reference, 60) == datetime(2026, 10, 21, 20, 0),
        "the next full hour is used",
    )
    check(
        next_hour_occurrence(datetime(2026, 10, 21, 20, 0, 0), 60) == datetime(2026, 10, 21, 21, 0),
        "a run exactly at the hour moves to the next hour",
    )
    check(
        next_hour_occurrence(reference, 120) == datetime(2026, 10, 21, 20, 0),
        "an interval of two hours uses the two hour grid",
    )
    check(
        next_hour_occurrence(datetime(2026, 10, 21, 23, 30), 60) == datetime(2026, 10, 22, 0, 0),
        "the next hour is used after midnight",
    )

    print("the next run from a fixed start time")
    check(
        next_anchor_occurrence(reference, "06:30", 90) == datetime(2026, 10, 21, 20, 0),
        "the interval continues from the start time",
    )
    check(
        next_anchor_occurrence(reference, "20:00", 60) == datetime(2026, 10, 21, 20, 0),
        "the start time of today is used",
    )
    check(
        next_anchor_occurrence(reference, "05:00", 60) == datetime(2026, 10, 21, 20, 0),
        "the start time of today is already past, the hour grid continues",
    )
    check(
        next_anchor_occurrence(datetime(2026, 10, 21, 23, 30), "06:30", 60)
        == datetime(2026, 10, 22, 0, 30),
        "the interval continues over midnight",
    )
    check(
        next_anchor_occurrence(datetime(2026, 10, 21, 23, 30), "06:30", 120)
        == datetime(2026, 10, 22, 0, 30),
        "the interval continues over midnight",
    )
    check(
        next_anchor_occurrence(datetime(2026, 10, 21, 23, 30), "23:00", 120)
        == datetime(2026, 10, 22, 1, 0),
        "the start time of the next day is used",
    )

    print("the interval mode")
    plain = Config()
    plain.schedule_mode = MODE_INTERVAL
    plain.interval_min = 30
    check(
        next_run_time(reference, plain) == datetime(2026, 10, 21, 20, 17, 12),
        "the next run is one interval away",
    )
    check(
        next_run_time(reference, plain, datetime(2026, 10, 21, 19, 50))
        == datetime(2026, 10, 21, 20, 20),
        "the interval is counted from the last run",
    )


def test_scheduler():
    print("scheduler")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.json")
        store = ConfigStore(path)
        store.update(run_duration_min=1, interval_min=30, stage=1, enabled=True, run_on_start=False)
        controller = HumidifierController(simulate=True)
        scheduler = Scheduler(store, controller)
        scheduler.start()
        time.sleep(0.5)

        state = scheduler.state()
        check(state["enabled"], "scheduler is enabled")
        check(state["next_run_at"] is not None, "a next run is scheduled")

        scheduler._execute_cycle(0, 1, "manual")
        check(not scheduler.state()["active"], "the cycle finished")
        check(not controller.status()["on"], "the humidifier is off after the cycle")

        store.update(interval_min=45)
        scheduler.settings_changed()
        state = scheduler.state()
        check(state["interval_min"] == 45, "the new interval is picked up")
        check(state["next_run_in_sec"] is not None, "the next run is recalculated")

        store.update(enabled=False)
        scheduler.settings_changed()
        time.sleep(0.3)
        check(scheduler.state()["next_run_at"] is None, "no run is scheduled while disabled")

        store.update(enabled=True, run_on_start=True)
        scheduler.settings_changed()
        state = scheduler.state()
        check(
            state["next_run_in_sec"] is not None and state["next_run_in_sec"] <= 1,
            "the schedule starts immediately when it is switched on",
        )

        store.update(run_on_start=False)
        scheduler.settings_changed()
        state = scheduler.state()
        check(
            state["next_run_in_sec"] is not None and state["next_run_in_sec"] > 60,
            "without 'run on start' the next run is postponed",
        )

        store.update(run_duration_min=30)
        scheduler.settings_changed()
        state = scheduler.state()
        check(state["run_duration_min"] == 30, "the new duration is taken over")

        scheduler.stop()


def test_missed_run_recovery():
    print("missed run recovery")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.json")
        store = ConfigStore(path)
        past = (datetime.now() - timedelta(hours=5)).isoformat(timespec="seconds")
        store.update(enabled=True, interval_min=60, next_run_at=past, last_run_at=past, run_on_start=False)
        controller = HumidifierController(simulate=True)
        scheduler = Scheduler(store, controller)
        scheduler._restore_state()
        state = scheduler.state()
        check(state["next_run_in_sec"] is not None, "the missed run is scheduled immediately")
        check(state["next_run_in_sec"] <= 1, "the missed run is not postponed")


def test_hour_alignment():
    print("hour alignment")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.json")
        store = ConfigStore(path)
        store.update(enabled=True, interval_min=60, schedule_mode=MODE_HOUR, run_on_start=False)
        controller = HumidifierController(simulate=True)
        scheduler = Scheduler(store, controller)
        scheduler._restore_state()
        state = scheduler.state()
        check(state["effective_mode"] == MODE_HOUR, "the schedule runs on full hours")
        scheduled = datetime.fromisoformat(state["next_run_at"])
        check(scheduled.minute == 0 and scheduled.second == 0, "the next run starts exactly at the hour")
        check(scheduled > datetime.now(), "the next run is in the future")
        check(
            scheduled <= next_hour_occurrence(datetime.now(), 60) + timedelta(seconds=30),
            "the next run is the coming full hour",
        )

        store.update(schedule_mode=MODE_ANCHOR, start_time="07:15")
        scheduler.settings_changed()
        state = scheduler.state()
        check(state["effective_mode"] == MODE_ANCHOR, "the fixed start time is active")
        scheduled = datetime.fromisoformat(state["next_run_at"])
        check(scheduled.minute == 15, "the next run starts at the configured minute")
        check(scheduled.hour % 1 == 0, "the next run is calculated from the start time")


if __name__ == "__main__":
    test_config_persistence()
    test_schedule_modes()
    test_scheduler()
    test_missed_run_recovery()
    test_hour_alignment()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        sys.exit(1)
    print("all checks passed")
