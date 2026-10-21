# Humidifier web interface

A small web application for the Raspberry Pi that drives the humidifier
connected to the GPIO pins.  It replaces the old cron/screen based scheduler
with a systemd service that publishes a web interface on port 80.

## Features

* **Operating duration** – how long the humidifier runs each time it is
  switched on (1 – 1440 minutes).
* **Interval** – how often the humidifier switches on automatically
  (1 – 1440 minutes, e.g. every hour, every two hours, ...).
* **Schedule mode** – when the automatic runs happen:
  * *On full hours* – the humidifier only starts at whole hours.  With an
    interval of two hours the runs are at 00:00, 02:00, 04:00 …, with an
    interval of one hour at every full hour.
  * *Starting at a fixed time* – the first run happens at the given time of
    the day and the interval is counted from there, e.g. 06:30 with an
    interval of 90 minutes gives 06:30, 08:00, 09:30 …
  * *Interval after the last run* – the humidifier restarts the interval
    after every run (the previous behaviour).
* **Power stage** – stage 1 (highest), 2 (medium) or 3 (lowest).
* **Manual control** – start a cycle immediately or switch the humidifier off.
* **Persistent configuration** – every setting is written to `config.json`
  and restored automatically when the Raspberry Pi reboots.
* **Missed runs are recovered** – if the Pi was switched off while a run was
  due, the cycle is executed shortly after the service starts again.
* **Activity log** – every action is written to `logs/app.log` and shown in
  the web interface.

## Layout

```
web/
├── app.py                 Flask application, JSON API and the HTTP server
├── config_store.py        Atomic, persistent JSON configuration
├── controller.py          Thread safe access to the GPIO driver
├── schedule.py            Calculation of the next run (hour grid, start time)
├── scheduler.py           Run cycle logic and next run calculation
├── logging_setup.py       Rotating log file plus an in-memory event buffer
├── run.sh                 Entry point used by systemd
├── setup.sh               Creates the virtual environment
├── deploy/
│   ├── install.sh         Installs nginx, systemd unit and dependencies
│   ├── humidifier-web.service
│   └── nginx-humidifier.conf
├── templates/index.html   The web interface
├── static/                CSS, JavaScript and the favicon
└── tests/smoke_test.py    Logic test that runs without hardware
```

## Installation on the Raspberry Pi

```bash
cd /home/pi/Desktop/humidifier/web
sudo bash deploy/install.sh
```

The script installs nginx, creates the python environment, installs the
systemd unit, stops the legacy scheduler and starts everything.  The
interface is then available at `http://<pi-ip>/`.

Update the application afterwards with:

```bash
scp -r web pi@<pi-ip>:/home/pi/Desktop/humidifier/
ssh pi@<pi-ip> "sudo systemctl restart humidifier-web"
```

## Service management

```bash
sudo systemctl status humidifier-web     # status
sudo systemctl restart humidifier-web    # restart
sudo systemctl stop humidifier-web       # stop
journalctl -u humidifier-web -f          # live log
```

The service is enabled, so it starts automatically after a reboot.  nginx is
enabled as well.

## Configuration file

`/home/pi/Desktop/humidifier/web/config.json`

| Setting                 | Meaning                                          |
| ----------------------- | ------------------------------------------------ |
| `run_duration_min`      | Minutes the humidifier runs per cycle            |
| `interval_min`          | Minutes between two automatic runs               |
| `schedule_mode`         | `hour`, `anchor` or `interval`                   |
| `start_time`            | Start time of the day for the `anchor` mode      |
| `stage`                 | 1 = highest, 2 = medium, 3 = lowest              |
| `enabled`               | Automatic schedule on/off                         |
| `run_on_start`          | Run immediately after a restart                   |
| `basic_auth_enabled`    | Protect the page with a password                  |
| `basic_auth_user`       | User name for the password protection             |
| `basic_auth_password`   | Password for the password protection              |
| `last_run_at`           | Timestamp of the last cycle                       |
| `next_run_at`           | Timestamp of the next automatic run               |
| `last_result`           | Result of the last cycle                          |

The file is written atomically, a copy of the last valid revision is kept in
`config.json.bak`.

The schedule on full hours needs an interval that is a whole number of hours.
If a different interval is chosen the schedule falls back to the plain
interval and the web interface shows a warning.

## HTTP API

| Method | Path                 | Description                                   |
| ------ | -------------------- | --------------------------------------------- |
| GET    | `/api/state`         | Configuration, scheduler and device status     |
| GET    | `/api/settings`      | Current configuration                          |
| POST   | `/api/settings`      | Save the configuration                          |
| POST   | `/api/humidifier/on` | Start a cycle (`duration_min`, `stage`)        |
| POST   | `/api/humidifier/off`| Stop the running cycle and switch the device off|
| GET    | `/api/logs`          | Recent log entries                             |
| GET    | `/api/health`        | Health check (not password protected)          |

Example:

```bash
curl -X POST http://<pi-ip>/api/settings \
     -H 'Content-Type: application/json' \
     -d '{"run_duration_min": 20, "interval_min": 120, "stage": 1, "schedule_mode": "hour"}'
```

To run the humidifier every two hours, always at a full hour:

```bash
curl -X POST http://<pi-ip>/api/settings \
     -H 'Content-Type: application/json' \
     -d '{"interval_min": 120, "schedule_mode": "hour"}'
```

To run it every 90 minutes, starting at 06:30 in the morning:

```bash
curl -X POST http://<pi-ip>/api/settings \
     -H 'Content-Type: application/json' \
     -d '{"interval_min": 90, "schedule_mode": "anchor", "start_time": "06:30"}'
```

## Tests

```bash
python3 tests/smoke_test.py
```

The test covers the configuration persistence, the validation of the input
and the scheduling logic.  It runs in simulation mode, so no hardware and no
network connection is required.

## Troubleshooting

**The humidifier does not react** – check `journalctl -u humidifier-web`.
The status pin (GPIO 27) reports whether the device is running.

**"GPIO busy" errors** – another program is using the pins.  The legacy
scheduler has to be stopped, the install script does that for you:

```bash
crontab -l | grep -v start_scheduler.sh | crontab -
pkill -f driver/scheduler.py
```

**The page does not open** – check `systemctl status nginx` and
`sudo nginx -t`.
