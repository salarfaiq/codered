#!/usr/bin/env python3
"""
Daily stats tracking with streak history.
Stores data in ~/.claude-led-stats.json
"""

import json
import os
from datetime import datetime, timedelta

STATS_PATH = os.path.expanduser("~/.claude-led-stats.json")


def _load():
    if os.path.exists(STATS_PATH):
        with open(STATS_PATH, "r") as f:
            return json.load(f)
    return {"days": {}}


def _save(data):
    with open(STATS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _ensure_day(data, day):
    if day not in data["days"]:
        data["days"][day] = {"approvals": 0, "pushes": 0}


def increment_approvals():
    data = _load()
    day = _today()
    _ensure_day(data, day)
    data["days"][day]["approvals"] += 1
    _save(data)
    return data["days"][day]["approvals"]


def increment_pushes():
    data = _load()
    day = _today()
    _ensure_day(data, day)
    data["days"][day]["pushes"] += 1
    _save(data)
    return data["days"][day]["pushes"]


def get_today():
    data = _load()
    day = _today()
    _ensure_day(data, day)
    return data["days"][day]


def get_streak():
    data = _load()
    if not data["days"]:
        return 0
    today = datetime.now().date()
    streak = 0
    check = today
    while True:
        key = check.strftime("%Y-%m-%d")
        day_data = data["days"].get(key)
        if day_data and (day_data["approvals"] > 0 or day_data["pushes"] > 0):
            streak += 1
            check -= timedelta(days=1)
        else:
            break
    return streak


def get_history(last_n=7):
    data = _load()
    today = datetime.now().date()
    result = []
    for i in range(last_n):
        d = today - timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        day_data = data["days"].get(key, {"approvals": 0, "pushes": 0})
        result.append({"date": key, **day_data})
    return result
