"""Utilities to load latest run summary and available runs."""
from __future__ import annotations

import json
import os
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
DEBUG_DIR = os.path.join(PROJECT_ROOT, "Debug")


def list_runs() -> list[str]:
    if not os.path.isdir(OUTPUT_DIR):
        return []
    runs = [d for d in os.listdir(OUTPUT_DIR) if os.path.isdir(os.path.join(OUTPUT_DIR, d))]
    # Expect folder name like YYYY-MM-DD_HH-MM-SS
    runs.sort(reverse=True)
    return runs


def latest_run_folder() -> str | None:
    runs = list_runs()
    return runs[0] if runs else None


def load_summary(run_id: str | None = None) -> dict[str, Any] | None:
    run = run_id or latest_run_folder()
    if not run:
        return None
    path = os.path.join(OUTPUT_DIR, run, "summary.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def tail_app_log(lines: int = 200) -> list[str]:
    log_path = os.path.join(DEBUG_DIR, "cacti_automation.log")
    if not os.path.exists(log_path):
        return []
    try:
        with open(log_path, encoding="utf-8", errors="ignore") as f:
            data = f.readlines()
            return [x.rstrip("\n") for x in data[-lines:]]
    except Exception:
        return []
