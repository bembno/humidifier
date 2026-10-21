(function () {
  "use strict";

  const POLL_INTERVAL = 2000;
  const LOG_INTERVAL = 6000;

  const el = (id) => document.getElementById(id);

  const ui = {
    linkStatus: el("link-status"),
    linkText: el("link-text"),
    devicePill: el("device-pill"),
    clock: el("clock"),
    enabled: el("enabled"),
    enabledLabel: el("enabled-label"),
    duration: el("duration"),
    interval: el("interval"),
    stage: el("stage"),
    scheduleMode: el("schedule-mode"),
    startTime: el("start-time"),
    startTimeRow: el("start-time-row"),
    hourWarning: el("hour-warning"),
    runOnStart: el("run-on-start"),
    authEnabled: el("auth-enabled"),
    authUser: el("auth-user"),
    authPassword: el("auth-password"),
    authFields: el("auth-fields"),
    btnSave: el("btn-save"),
    saveState: el("save-state"),
    btnStart: el("btn-start"),
    btnStop: el("btn-stop"),
    btnRefreshLog: el("btn-refresh-log"),
    nextRun: el("next-run"),
    nextRunAt: el("next-run-at"),
    humidifierState: el("humidifier-state"),
    activeStage: el("active-stage"),
    lastRun: el("last-run"),
    lastResult: el("last-result"),
    nextRunAtShort: el("next-run-at-short"),
    scheduleModeLabel: el("schedule-mode-label"),
    uptime: el("uptime"),
    configFile: el("config-file"),
    stageBadge: el("stage-badge"),
    log: el("log"),
    toast: el("toast"),
    footerServer: el("footer-server"),
  };

  let state = null;
  let serverOffset = 0;
  let dirty = false;
  let toastTimer = null;

  function toast(message, isError) {
    ui.toast.textContent = message;
    ui.toast.classList.toggle("error", !!isError);
    ui.toast.classList.add("visible");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      ui.toast.classList.remove("visible");
    }, 2600);
  }

  function api(path, options) {
    return fetch(path, Object.assign({ cache: "no-store" }, options || {})).then(function (response) {
      if (response.status === 401) {
        ui.linkStatus.classList.remove("online");
        ui.linkStatus.classList.add("offline");
        ui.linkText.textContent = "unauthorised";
        throw new Error("authentication required");
      }
      return response.json().then(function (data) {
        if (!response.ok) {
          throw new Error(data.error || "request failed");
        }
        return data;
      });
    });
  }

  function setLink(online) {
    ui.linkStatus.classList.toggle("online", online);
    ui.linkStatus.classList.toggle("offline", !online);
    ui.linkText.textContent = online ? "connected" : "offline";
  }

  function formatDuration(seconds) {
    if (seconds === null || seconds === undefined || isNaN(seconds)) {
      return "--:--:--";
    }
    const total = Math.max(0, Math.floor(seconds));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    const pad = (n) => String(n).padStart(2, "0");
    return pad(hours) + ":" + pad(minutes) + ":" + pad(secs);
  }

  function formatTimestamp(value) {
    if (!value) {
      return "never";
    }
    const date = new Date(value);
    if (isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString();
  }

  function formatUptime(seconds) {
    const total = Math.max(0, Math.floor(seconds || 0));
    const days = Math.floor(total / 86400);
    const hours = Math.floor((total % 86400) / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    if (days > 0) {
      return days + "d " + hours + "h";
    }
    if (hours > 0) {
      return hours + "h " + minutes + "m";
    }
    return minutes + "m " + (total % 60) + "s";
  }

  function syncForm(config) {
    if (dirty) {
      return;
    }
    ui.duration.value = config.run_duration_min;
    ui.interval.value = config.interval_min;
    ui.stage.value = String(config.stage);
    ui.scheduleMode.value = config.schedule_mode || "hour";
    ui.startTime.value = config.start_time || "06:00";
    ui.enabled.checked = !!config.enabled;
    ui.runOnStart.checked = !!config.run_on_start;
    ui.authEnabled.checked = !!config.basic_auth_enabled;
    ui.authUser.value = config.basic_auth_user || "";
    ui.authPassword.value = "";
    ui.authPassword.placeholder = config.basic_auth_password_set
      ? "password (unchanged)"
      : "password";
    ui.authFields.classList.toggle("hidden", !config.basic_auth_enabled);
    updateEnabledLabel();
    updateScheduleMode();
    highlightChips();
  }

  function updateEnabledLabel() {
    ui.enabledLabel.textContent = ui.enabled.checked ? "Enabled" : "Disabled";
  }

  function updateScheduleMode() {
    const mode = ui.scheduleMode.value;
    ui.startTimeRow.classList.toggle("hidden", mode !== "anchor");
    const interval = Number(ui.interval.value) || 0;
    const needsWholeHours = mode === "hour" && interval % 60 !== 0;
    ui.hourWarning.classList.toggle("hidden", !needsWholeHours);
  }

  function highlightChips() {
    document.querySelectorAll("#duration-chips .chip").forEach(function (chip) {
      chip.classList.toggle("active", Number(chip.dataset.value) === Number(ui.duration.value));
    });
    document.querySelectorAll("#interval-chips .chip").forEach(function (chip) {
      chip.classList.toggle("active", Number(chip.dataset.value) === Number(ui.interval.value));
    });
  }

  function render(state) {
    const config = state.config;
    const scheduler = state.scheduler;
    const humidifier = state.humidifier;

    syncForm(config);

    const on = !!humidifier.on;
    ui.devicePill.textContent = on ? "running" : "standby";
    ui.devicePill.className = "pill " + (on ? "pill-on" : "pill-off");
    ui.stageBadge.textContent = scheduler.active ? "stage " + scheduler.current_stage : "idle";
    ui.stageBadge.className = "pill " + (scheduler.active ? "pill-on" : "pill-muted");

    ui.humidifierState.textContent = on ? "on" : "off";
    ui.activeStage.textContent = scheduler.active
      ? "stage " + scheduler.current_stage
      : "not active";
    ui.lastRun.textContent = formatTimestamp(scheduler.last_run_at);
    ui.lastResult.textContent = scheduler.last_result || "-";
    ui.scheduleModeLabel.textContent = scheduler.mode_label || "-";
    ui.nextRunAtShort.textContent = scheduler.next_run_at
      ? new Date(scheduler.next_run_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      : "-";
    ui.uptime.textContent = formatUptime(scheduler.uptime_sec);
    ui.configFile.textContent = state.config_file;
    ui.footerServer.textContent = "server time " + state.server_time.replace("T", " ");

    if (scheduler.next_run_at) {
      ui.nextRunAt.textContent = "at " + formatTimestamp(scheduler.next_run_at);
      ui.nextRun.classList.remove("idle");
    } else {
      ui.nextRunAt.textContent = "no run scheduled";
      ui.nextRun.classList.add("idle");
    }

    if (scheduler.active) {
      ui.nextRun.textContent = "running";
      ui.nextRun.classList.remove("idle");
    }

    ui.btnStart.disabled = !!scheduler.active;
    ui.btnStop.disabled = !on && !scheduler.active;
  }

  function tickCountdown() {
    if (!state) {
      return;
    }
    const scheduler = state.scheduler;
    if (scheduler.active) {
      ui.nextRun.textContent = "running";
      return;
    }
    if (!scheduler.next_run_at) {
      ui.nextRun.textContent = "--:--:--";
      return;
    }
    const target = new Date(scheduler.next_run_at).getTime() + serverOffset;
    ui.nextRun.textContent = formatDuration((target - Date.now()) / 1000);
  }

  function loadState() {
    return api("/api/state")
      .then(function (data) {
        setLink(true);
        state = data;
        serverOffset = new Date(data.server_time).getTime() - Date.now();
        render(data);
      })
      .catch(function (error) {
        setLink(false);
        if (error && error.message === "authentication required") {
          return;
        }
      });
  }

  function loadLog() {
    return api("/api/logs?limit=60")
      .then(function (data) {
        const events = data.events || [];
        ui.log.innerHTML = "";
        events.forEach(function (event) {
          const item = document.createElement("li");
          item.className = "level-" + event.level;
          const ts = document.createElement("span");
          ts.className = "ts";
          ts.textContent = event.ts;
          const msg = document.createElement("span");
          msg.className = "msg";
          msg.textContent = event.message;
          item.appendChild(ts);
          item.appendChild(msg);
          ui.log.appendChild(item);
        });
      })
      .catch(function () {
        /* keep the last log */
      });
  }

  function saveSettings() {
    const payload = {
      run_duration_min: Number(ui.duration.value),
      interval_min: Number(ui.interval.value),
      stage: Number(ui.stage.value),
      enabled: ui.enabled.checked,
      run_on_start: ui.runOnStart.checked,
      schedule_mode: ui.scheduleMode.value,
      start_time: ui.scheduleMode.value === "anchor" ? ui.startTime.value : "",
      basic_auth_enabled: ui.authEnabled.checked,
      basic_auth_user: ui.authUser.value,
      basic_auth_password: ui.authPassword.value,
    };
    if (!payload.run_duration_min || payload.run_duration_min < 1) {
      toast("The operating duration must be at least 1 minute", true);
      return;
    }
    if (!payload.interval_min || payload.interval_min < 1) {
      toast("The interval must be at least 1 minute", true);
      return;
    }
    if (payload.schedule_mode === "hour" && payload.interval_min % 60 !== 0) {
      toast(
        "Running on full hours needs a whole number of hours, the schedule uses the interval instead",
        true
      );
    }
    api("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function () {
        dirty = false;
        ui.saveState.textContent = "saved";
        ui.saveState.classList.remove("error");
        ui.saveState.classList.add("visible");
        window.setTimeout(function () {
          ui.saveState.classList.remove("visible");
        }, 2200);
        toast("Settings saved");
        return loadState();
      })
      .catch(function (error) {
        ui.saveState.textContent = "error";
        ui.saveState.classList.add("error", "visible");
        toast(error.message || "Could not save the settings", true);
      });
  }

  function markDirty() {
    dirty = true;
    highlightChips();
    updateScheduleMode();
  }

  function bindChips(containerId, input) {
    document.querySelectorAll("#" + containerId + " .chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        input.value = chip.dataset.value;
        markDirty();
      });
    });
  }

  function bind() {
    bindChips("duration-chips", ui.duration);
    bindChips("interval-chips", ui.interval);

    [ui.duration, ui.interval, ui.stage, ui.runOnStart, ui.authEnabled, ui.authUser, ui.authPassword, ui.startTime].forEach(
      function (input) {
        input.addEventListener("input", markDirty);
        input.addEventListener("change", markDirty);
      }
    );

    ui.scheduleMode.addEventListener("change", function () {
      updateScheduleMode();
      markDirty();
    });

    ui.interval.addEventListener("input", updateScheduleMode);

    ui.enabled.addEventListener("change", function () {
      updateEnabledLabel();
      markDirty();
    });

    ui.authEnabled.addEventListener("change", function () {
      ui.authFields.classList.toggle("hidden", !ui.authEnabled.checked);
      markDirty();
    });

    ui.btnSave.addEventListener("click", saveSettings);

    ui.btnStart.addEventListener("click", function () {
      api("/api/humidifier/on", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          duration_min: Number(ui.duration.value),
          stage: Number(ui.stage.value),
        }),
      })
        .then(function () {
          toast("The humidifier was switched on");
          return loadState();
        })
        .catch(function (error) {
          toast(error.message || "Could not switch the humidifier on", true);
        });
    });

    ui.btnStop.addEventListener("click", function () {
      api("/api/humidifier/off", { method: "POST" })
        .then(function () {
          toast("The humidifier was switched off");
          return loadState();
        })
        .catch(function (error) {
          toast(error.message || "Could not switch the humidifier off", true);
        });
    });

    ui.btnRefreshLog.addEventListener("click", loadLog);

    window.setInterval(loadState, POLL_INTERVAL);
    window.setInterval(loadLog, LOG_INTERVAL);
    window.setInterval(tickCountdown, 1000);
    window.setInterval(function () {
      ui.clock.textContent = new Date(Date.now() + serverOffset).toLocaleTimeString();
    }, 1000);

    ui.clock.textContent = new Date().toLocaleTimeString();
  }

  bind();
  loadState();
  loadLog();
})();
