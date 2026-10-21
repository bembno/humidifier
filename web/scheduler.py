"""Scheduling logic for the humidifier.

The scheduler is a single background thread that owns the humidifier.  It

* restores the persisted schedule when the service starts,
* runs the humidifier for the configured duration at the configured stage,
* switches it off again afterwards,
* schedules the next automatic run and
* persists the next run time so that a reboot does not lose the schedule.

All time calculations use the local wall clock so that the schedule stays
meaningful across reboots and daylight saving changes.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from config_store import Config, ConfigStore, from_iso, now, to_iso
from controller import HumidifierController, HumidifierError
from schedule import MODE_INTERVAL, MODE_LABELS, resolve_mode, next_run_time

LOG = logging.getLogger("humidifier.scheduler")

TICK_SECONDS = 2.0
MAX_WAIT_SECONDS = 30.0


class Scheduler:
    """Owns the humidifier and executes the configured run cycles."""

    def __init__(self, config_store: ConfigStore, controller: HumidifierController) -> None:
        self._config = config_store
        self._controller = controller
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pending_manual: Optional[Dict[str, Any]] = None
        self._interrupt = False
        self._active = False
        self._current_stage: Optional[int] = None
        self._reason = ""
        self._next_run: Optional[datetime] = None
        self._last_run: Optional[datetime] = None
        self._last_result = ""
        self._started_at = now()
        self._last_config: Optional[Config] = None

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="humidifier-scheduler", daemon=True)
        self._thread.start()
        LOG.info("Scheduler thread started")

    def stop(self, timeout: float = 10.0) -> None:
        self._stop_event.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        try:
            self._controller.turn_off()
        except HumidifierError:
            pass

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def trigger_manual(self, duration_min: Optional[int] = None, stage: Optional[int] = None) -> None:
        """Queue a run cycle that starts as soon as the humidifier is free."""
        config = self._config.load()
        with self._lock:
            self._pending_manual = {
                "duration_min": duration_min or config.run_duration_min,
                "stage": stage or config.stage,
            }
        LOG.info("Manual run queued (duration %s min, stage %s)", self._pending_manual["duration_min"],
                 self._pending_manual["stage"])
        self._wake.set()

    def stop_current_run(self) -> None:
        """Interrupt the running cycle and switch the humidifier off."""
        with self._lock:
            self._interrupt = True
            if not self._active:
                try:
                    self._controller.turn_off()
                except HumidifierError:
                    pass
        self._wake.set()

    def settings_changed(self) -> None:
        """Recalculate the next automatic run after the user changed settings."""
        config = self._config.load()
        with self._lock:
            previous = self._last_config
            self._last_config = config
            changed = self._reconcile_schedule(config, previous)
        if changed:
            self._persist_next_run()
        self._wake.set()

    def state(self) -> Dict[str, Any]:
        config = self._config.load()
        with self._lock:
            next_run = self._next_run
            active = self._active
            pending = self._pending_manual is not None
            stage = self._current_stage
            reason = self._reason
            last_run = self._last_run
            last_result = self._last_result
        seconds_until = None
        if next_run is not None:
            seconds_until = int((next_run - now()).total_seconds())
        return {
            "enabled": config.enabled,
            "active": active,
            "pending_manual": pending,
            "next_run_at": to_iso(next_run),
            "next_run_in_sec": seconds_until,
            "last_run_at": to_iso(last_run),
            "last_result": last_result,
            "current_stage": stage,
            "reason": reason,
            "started_at": to_iso(self._started_at),
            "uptime_sec": int((now() - self._started_at).total_seconds()),
            "run_duration_min": config.run_duration_min,
            "interval_min": config.interval_min,
            "schedule_mode": config.schedule_mode,
            "effective_mode": resolve_mode(config),
            "mode_label": MODE_LABELS.get(resolve_mode(config), ""),
            "start_time": config.start_time,
        }

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _run(self) -> None:
        self._restore_state()
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                LOG.exception("Unexpected error in the scheduler loop")
                self._stop_event.wait(5.0)
        LOG.info("Scheduler thread stopped")

    def _restore_state(self) -> None:
        config = self._config.load()
        with self._lock:
            self._last_run = from_iso(config.last_run_at)
            self._last_result = config.last_result or ""
            self._last_config = config
            stored_next = from_iso(config.next_run_at)
        if not config.enabled:
            with self._lock:
                self._next_run = None
            LOG.info("Scheduler is disabled, waiting for the user to enable it")
            return
        if config.run_on_start:
            next_run = now()
            LOG.info("Running immediately because 'run on start' is enabled")
        elif stored_next is not None and stored_next > now():
            next_run = stored_next
            LOG.info("Restored schedule, next run at %s", next_run.strftime("%Y-%m-%d %H:%M:%S"))
        elif stored_next is not None:
            next_run = now()
            LOG.info("The scheduled run was missed while the system was off, running now")
        else:
            next_run = next_run_time(now(), config, self._last_run)
            LOG.info(
                "Next run scheduled for %s (%s)",
                next_run.strftime("%Y-%m-%d %H:%M:%S"),
                MODE_LABELS.get(resolve_mode(config), ""),
            )
        with self._lock:
            self._next_run = next_run
        self._persist_next_run()

    def _tick(self) -> None:
        config = self._config.load()
        with self._lock:
            previous = self._last_config
            self._last_config = config
            changed = self._reconcile_schedule(config, previous)
        if changed:
            self._persist_next_run()
        manual = self._take_manual()
        if manual is not None:
            self._execute_cycle(manual["duration_min"], manual["stage"], "manual")
            return
        if not config.enabled:
            with self._lock:
                if self._next_run is not None:
                    self._next_run = None
                    self._persist_next_run()
            self._wait(TICK_SECONDS)
            return
        with self._lock:
            next_run = self._next_run
        if next_run is None:
            next_run = next_run_time(now(), config, self._last_run)
            with self._lock:
                self._next_run = next_run
            self._persist_next_run()
        remaining = (next_run - now()).total_seconds()
        if remaining <= 0:
            self._execute_cycle(config.run_duration_min, config.stage, "scheduled")
            return
        self._wait(min(remaining, MAX_WAIT_SECONDS))

    def _reconcile_schedule(self, config: Config, previous: Optional[Config]) -> bool:
        """Keep the next run in sync with the configuration.

        * the schedule was switched on  -> the first run follows the
          "run immediately" setting,
        * the interval, the mode or the start time changed -> the schedule is
          calculated again,
        * only the duration or the stage changed -> the next run stays as it is.
        """
        if not config.enabled:
            changed = self._next_run is not None
            self._next_run = None
            return changed
        if previous is None:
            return False
        if not previous.enabled:
            self._next_run = (
                now()
                if config.run_on_start
                else next_run_time(now(), config, None)
            )
            return True
        if (
            previous.interval_min != config.interval_min
            or previous.schedule_mode != config.schedule_mode
            or previous.start_time != config.start_time
        ):
            self._next_run = next_run_time(now(), config, None)
            return True
        if previous.run_on_start != config.run_on_start:
            self._next_run = (
                now() if config.run_on_start else next_run_time(now(), config, None)
            )
            return True
        return False

    def _take_manual(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            manual = self._pending_manual
            self._pending_manual = None
            return manual

    def _execute_cycle(self, duration_min: int, stage: int, reason: str) -> None:
        config = self._config.load()
        start = now()
        with self._lock:
            self._interrupt = False
            self._active = True
            self._current_stage = stage
            self._reason = reason
            self._last_run = start
        if reason == "scheduled":
            next_run = self._next_run_after(config, start, duration_min)
            with self._lock:
                self._next_run = next_run
            self._persist_next_run()
        LOG.info("Starting %s cycle: %s min, stage %s", reason, duration_min, stage)
        self._persist_run_info(start)
        result = "completed"
        try:
            self._controller.turn_on(stage)
            deadline = time.monotonic() + max(0, duration_min) * 60
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                with self._lock:
                    interrupted = self._interrupt
                if interrupted:
                    result = "stopped by user"
                    break
                if self._stop_event.wait(min(1.0, remaining)):
                    result = "interrupted by shutdown"
                    break
            try:
                self._controller.turn_off()
            except HumidifierError as exc:
                LOG.error("The humidifier could not be switched off: %s", exc)
                result = "error while switching off"
        except HumidifierError as exc:
            LOG.error("The humidifier could not be switched on: %s", exc)
            result = f"error: {exc}"
        finally:
            with self._lock:
                self._active = False
                self._current_stage = None
                self._reason = ""
                self._interrupt = False
                self._last_result = result
            self._persist_run_info(start, result)
        LOG.info("Cycle finished (%s)", result)

    def _next_run_after(self, config: Config, start: datetime, duration_min: int) -> datetime:
        """The next automatic run after a cycle that started at ``start``.

        On the hour and on a fixed start time the next run is the next point
        of the grid after the cycle has finished, so that two cycles can
        never overlap.
        """
        if resolve_mode(config) == MODE_INTERVAL:
            return start + timedelta(minutes=config.interval_min)
        end = start + timedelta(minutes=max(0, duration_min))
        return next_run_time(end, config, None)

    def _persist_run_info(self, start: datetime, result: Optional[str] = None) -> None:
        try:
            self._config.update(last_run_at=to_iso(start), last_result=result)
        except Exception:
            LOG.exception("Unable to persist the run information")

    def _persist_next_run(self) -> None:
        with self._lock:
            next_run = self._next_run
        try:
            self._config.update(next_run_at=to_iso(next_run))
        except Exception:
            LOG.exception("Unable to persist the next run time")

    def _wait(self, seconds: float) -> None:
        self._wake.wait(timeout=max(0.0, seconds))
        self._wake.clear()
