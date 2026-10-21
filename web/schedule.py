"""Calculation of the next automatic run.

Three schedules are supported:

``hour``
    The humidifier only switches on at full hours.  The runs are placed on
    the hour grid of the day, an interval of two hours gives 00:00, 02:00,
    04:00 ... (or any other whole hour grid).

``anchor``
    The humidifier switches on for the first time at the configured start
    time and repeats the interval from there, for example 06:30 with an
    interval of 90 minutes gives 06:30, 08:00, 09:30 ...

``interval``
    The humidifier switches on the interval after the last run.

The helpers only work with plain values so that they can be tested without
the hardware and without the rest of the application.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional, Tuple

MODE_HOUR = "hour"
MODE_ANCHOR = "anchor"
MODE_INTERVAL = "interval"

MODES = (MODE_HOUR, MODE_ANCHOR, MODE_INTERVAL)

MODE_LABELS = {
    MODE_HOUR: "full hours",
    MODE_ANCHOR: "fixed start time",
    MODE_INTERVAL: "interval after the last run",
}


def parse_start_time(value: Optional[str]) -> Optional[Tuple[int, int]]:
    """Return the hour and minute of a ``HH:MM`` string or None."""
    if not value:
        return None
    parts = str(value).strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def resolve_mode(config) -> str:
    """Return the mode that is actually used for the given configuration.

    A schedule on full hours is only possible with an interval that is a
    whole number of hours.  If that is not the case the schedule falls back
    to the plain interval so that the humidifier never misses a run.
    """
    mode = getattr(config, "schedule_mode", MODE_HOUR)
    interval = int(getattr(config, "interval_min", 60))
    if mode == MODE_ANCHOR:
        if parse_start_time(getattr(config, "start_time", "")):
            return MODE_ANCHOR
        return MODE_HOUR if interval % 60 == 0 else MODE_INTERVAL
    if mode == MODE_HOUR and interval % 60 == 0:
        return MODE_HOUR
    return MODE_INTERVAL


def next_hour_occurrence(now: datetime, interval_min: int) -> datetime:
    """The next full hour that fits the interval grid of the day."""
    interval = max(60, interval_min)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    steps = int(math.ceil(24 * 60 / interval)) + 1
    for step in range(steps + 1):
        candidate = midnight + timedelta(minutes=step * interval)
        if candidate > now:
            return candidate
    return now + timedelta(hours=1)


def next_anchor_occurrence(now: datetime, start_time: str, interval_min: int) -> datetime:
    """The next occurrence of the start time plus a multiple of the interval."""
    parsed = parse_start_time(start_time) or (0, 0)
    hour, minute = parsed
    interval = max(1, interval_min)
    best: Optional[datetime] = None
    for day_offset in (-1, 0, 1):
        day = (now + timedelta(days=day_offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        difference = (now - day).total_seconds() / 60.0
        steps = max(0, int(math.ceil(difference / interval)))
        for step in (steps, steps + 1):
            candidate = day + timedelta(minutes=step * interval)
            if candidate > now and (best is None or candidate < best):
                best = candidate
    return best or (now + timedelta(minutes=interval))


def next_run_time(now: datetime, config, last_run: Optional[datetime] = None) -> datetime:
    """The next automatic run according to the configuration."""
    mode = resolve_mode(config)
    interval = int(getattr(config, "interval_min", 60))
    if mode == MODE_ANCHOR:
        return next_anchor_occurrence(now, getattr(config, "start_time", ""), interval)
    if mode == MODE_HOUR:
        return next_hour_occurrence(now, interval)
    if last_run is not None:
        candidate = last_run + timedelta(minutes=interval)
        if candidate > now:
            return candidate
    return now + timedelta(minutes=interval)
