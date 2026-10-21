"""Flask application that exposes the humidifier web interface.

Run with:

    python app.py

The HTTP server is waitress (pure python, no compilation needed on a
Raspberry Pi).  It listens on 127.0.0.1 only; the public access is provided
by the nginx web server that is installed as a reverse proxy.
"""

from __future__ import annotations

import functools
import hmac
import logging
import os
import signal
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from flask import Flask, jsonify, render_template, request

from config_store import ConfigError, ConfigStore
from controller import HumidifierController
from logging_setup import configure_logging, recent_events
from scheduler import Scheduler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOST = os.environ.get("HUMIDIFIER_HOST", "127.0.0.1")
PORT = int(os.environ.get("HUMIDIFIER_PORT", "8080"))

LOG = logging.getLogger("humidifier.web")


def create_app(
    config_store: Optional[ConfigStore] = None,
    controller: Optional[HumidifierController] = None,
    start_scheduler: bool = True,
) -> Flask:
    configure_logging()
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["JSON_SORT_KEYS"] = False

    store = config_store or ConfigStore()
    humidifier = controller or HumidifierController()
    scheduler = Scheduler(store, humidifier)

    app.extensions["config_store"] = store
    app.extensions["controller"] = humidifier
    app.extensions["scheduler"] = scheduler

    try:
        humidifier.initialize()
    except Exception as exc:
        LOG.error("The GPIO driver could not be initialised: %s", exc)

    def require_auth(view: Callable) -> Callable:
        @functools.wraps(view)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            config = store.load()
            if config.basic_auth_enabled:
                auth = request.authorization
                username = (auth.username or "") if auth else ""
                password = (auth.password or "") if auth else ""
                valid_user = hmac.compare_digest(username, config.basic_auth_user)
                valid_pass = hmac.compare_digest(password, config.basic_auth_password)
                if not (valid_user and valid_pass):
                    return (
                        jsonify({"error": "authentication required"}),
                        401,
                        {"WWW-Authenticate": 'Basic realm="Humidifier"'},
                    )
            return view(*args, **kwargs)

        return wrapper

    @app.route("/")
    @require_auth
    def index() -> Any:
        return render_template("index.html")

    @app.route("/api/state")
    @require_auth
    def api_state() -> Any:
        config = store.load()
        public = config.to_dict()
        public["basic_auth_password"] = ""
        public["basic_auth_password_set"] = bool(config.basic_auth_password)
        return jsonify(
            {
                "config": public,
                "scheduler": scheduler.state(),
                "humidifier": humidifier.status(),
                "server_time": datetime.now().isoformat(timespec="seconds"),
                "config_file": store.path,
            }
        )

    @app.route("/api/settings", methods=["GET", "POST"])
    @require_auth
    def api_settings() -> Any:
        if request.method == "GET":
            public = store.load().to_dict()
            public["basic_auth_password"] = ""
            public["basic_auth_password_set"] = bool(store.load().basic_auth_password)
            return jsonify(public)
        payload = request.get_json(silent=True) or {}
        allowed = {
            "run_duration_min",
            "interval_min",
            "stage",
            "enabled",
            "run_on_start",
            "schedule_mode",
            "start_time",
            "basic_auth_enabled",
            "basic_auth_user",
            "basic_auth_password",
        }
        changes: Dict[str, Any] = {}
        for key, value in payload.items():
            if key not in allowed:
                continue
            if key in ("run_duration_min", "interval_min", "stage"):
                try:
                    changes[key] = int(value)
                except (TypeError, ValueError):
                    return jsonify({"error": f"{key} must be a whole number"}), 400
            elif key in ("enabled", "run_on_start", "basic_auth_enabled"):
                changes[key] = bool(value)
            else:
                changes[key] = str(value)
        try:
            config = store.update(**changes)
        except ConfigError as exc:
            return jsonify({"error": str(exc)}), 400
        scheduler.settings_changed()
        LOG.info(
            "Settings updated: duration=%s min, interval=%s min, stage=%s, enabled=%s",
            config.run_duration_min,
            config.interval_min,
            config.stage,
            config.enabled,
        )
        public = config.to_dict()
        public["basic_auth_password"] = ""
        public["basic_auth_password_set"] = bool(config.basic_auth_password)
        return jsonify(public)

    @app.route("/api/humidifier/on", methods=["POST"])
    @require_auth
    def api_humidifier_on() -> Any:
        payload = request.get_json(silent=True) or {}
        duration = payload.get("duration_min")
        stage = payload.get("stage")
        try:
            duration = int(duration) if duration is not None else None
            stage = int(stage) if stage is not None else None
        except (TypeError, ValueError):
            return jsonify({"error": "duration_min and stage must be whole numbers"}), 400
        scheduler.trigger_manual(duration, stage)
        return jsonify({"status": "queued", "state": scheduler.state()})

    @app.route("/api/humidifier/off", methods=["POST"])
    @require_auth
    def api_humidifier_off() -> Any:
        scheduler.stop_current_run()
        return jsonify({"status": "stopped", "state": scheduler.state()})

    @app.route("/api/logs")
    @require_auth
    def api_logs() -> Any:
        try:
            limit = int(request.args.get("limit", "100"))
        except ValueError:
            limit = 100
        return jsonify({"events": recent_events(min(max(limit, 1), 300))})

    @app.route("/api/health")
    def api_health() -> Any:
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def not_found(error: Exception) -> Any:
        if request.path.startswith("/api/"):
            return jsonify({"error": "not found"}), 404
        return render_template("index.html"), 404

    if start_scheduler:
        scheduler.start()

    return app


app = create_app()


def _shutdown(signum: int, frame: Any) -> None:  # pragma: no cover - signal path
    LOG.info("Received signal %s, shutting down", signum)
    scheduler = app.extensions.get("scheduler")
    if scheduler is not None:
        scheduler.stop()
    os._exit(0)


def main() -> None:
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _shutdown)
        except ValueError:
            pass
    LOG.info("Starting the humidifier web interface on %s:%s", HOST, PORT)
    try:
        from waitress import serve
    except ImportError:
        LOG.exception("waitress is not installed, falling back to the built in server")
        app.run(host=HOST, port=PORT, threaded=True)
        return
    serve(app, host=HOST, port=PORT, threads=8, ident="humidifier-web")


if __name__ == "__main__":
    main()
