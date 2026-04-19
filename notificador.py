import datetime as dt
import json
import pathlib
import subprocess
from typing import Any

from formatadores import parse_date


def event_key(event: dict[str, Any]) -> str:
    return f"{event.get('id', '')}:{event.get('start', {}).get('dateTime', '')}"


def load_notify_state(state_file: pathlib.Path) -> dict[str, Any]:
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_notify_state(state_file: pathlib.Path, state: dict[str, Any]) -> None:
    state_file.write_text(json.dumps(state), encoding="utf-8")


def notify_event_if_needed(event: dict[str, Any], state_file: pathlib.Path) -> None:
    key = event_key(event)
    state = load_notify_state(state_file)
    if state.get("last_key") == key:
        return
    start = parse_date(event["start"]["dateTime"]).astimezone()
    now_local = dt.datetime.now().astimezone()
    mins = max(0, int((start - now_local).total_seconds() // 60))
    summary = event.get("summary", "(Sem titulo)")
    body = f"{start:%H:%M} - {summary}"
    subprocess.run(["notify-send", f"Agenda em {mins} min", body], check=False)
    save_notify_state(state_file, {"last_key": key})
