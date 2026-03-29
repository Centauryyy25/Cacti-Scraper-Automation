"""Centralized logging configuration for the project.

Usage:
    from utils.logging_config import setup_logging
    setup_logging(app_name="cacti_app")
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


def setup_logging(app_name: str = "cacti", log_dir: str = "Debug", level: int = logging.INFO,
                  propagate_third_party: bool = False) -> None:
    """Configure root logging once with console + rotating file handlers.

    - Logs to console and `log_dir` as `cacti_automation.log` with daily rotation.
    - Safe to call multiple times: won’t duplicate handlers.
    - Optionally reduces noisy third‑party logs.
    """
    root = logging.getLogger()

    if getattr(root, "_cacti_logging_configured", False):
        return

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "cacti_automation.log")

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmt)

    # Daily rotating file handler, keep 7 days
    fh = TimedRotatingFileHandler(log_path, when="midnight", backupCount=7, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)

    root.setLevel(level)
    root.addHandler(ch)
    root.addHandler(fh)

    # Add structured JSON-lines events handler for downstream dashboards
    try:
        events_path = os.path.join(log_dir, "events.jsonl")
        eh = TimedRotatingFileHandler(events_path, when="midnight", backupCount=7, encoding="utf-8")
        eh.setLevel(level)

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
                payload = {
                    "ts": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
                    "level": record.levelname,
                    "logger": record.name,
                    "msg": record.getMessage(),
                }
                extra_payload = getattr(record, "extra_payload", None)
                if isinstance(extra_payload, dict):
                    payload.update(extra_payload)
                return json.dumps(payload, ensure_ascii=False)

        eh.setFormatter(JsonFormatter())
        root.addHandler(eh)
    except Exception:
        # Do not fail app if JSON handler cannot be initialized
        pass

    # Tame noisy libs unless explicitly requested
    if not propagate_third_party:
        for noisy in ("urllib3", "selenium", "werkzeug", "easyocr"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    # Mark as configured
    root._cacti_logging_configured = True  # type: ignore[attr-defined]
