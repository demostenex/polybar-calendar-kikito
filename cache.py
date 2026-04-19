import datetime as dt
import json
import pathlib
from typing import Any


def load_cache(cache_file: pathlib.Path, ttl: int) -> list[dict[str, Any]] | None:
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    ts = data.get("timestamp")
    if not isinstance(ts, (int, float)):
        return None
    age = dt.datetime.now().timestamp() - ts
    if age > ttl:
        return None
    events = data.get("events")
    if not isinstance(events, list):
        return None
    return events


def save_cache(cache_file: pathlib.Path, events: list[dict[str, Any]]) -> None:
    payload = {
        "timestamp": dt.datetime.now().timestamp(),
        "events": events,
    }
    cache_file.write_text(json.dumps(payload), encoding="utf-8")
