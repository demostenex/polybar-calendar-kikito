import datetime as dt
from typing import Any


def now_utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def end_of_local_day_iso(days_ahead: int) -> str:
    now_local = dt.datetime.now().astimezone()
    target_date = now_local.date() + dt.timedelta(days=days_ahead)
    target = dt.datetime.combine(target_date, dt.time(23, 59, 59), tzinfo=now_local.tzinfo)
    return target.isoformat()


def parse_date(date_text: str) -> dt.datetime:
    if "T" not in date_text:
        parsed = dt.datetime.strptime(date_text, "%Y-%m-%d")
        return parsed.replace(tzinfo=dt.timezone.utc)
    return dt.datetime.fromisoformat(date_text.replace("Z", "+00:00"))


def format_event(event: dict[str, Any]) -> str:
    start_data = event.get("start", {})
    summary = event.get("summary", "(Sem titulo)")
    if "dateTime" in start_data:
        start = parse_date(start_data["dateTime"])
        local = start.astimezone()
        return f"{local:%d/%m %H:%M} - {summary}"
    if "date" in start_data:
        start = parse_date(start_data["date"]).astimezone()
        return f"{start:%d/%m} (dia todo) - {summary}"
    return summary


def short_event_text(event: dict[str, Any], max_len: int = 36) -> str:
    start_data = event.get("start", {})
    summary = event.get("summary", "(Sem titulo)")
    if "dateTime" in start_data:
        start = parse_date(start_data["dateTime"]).astimezone()
        text = f"{start:%H:%M} {summary}"
    elif "date" in start_data:
        text = f"dia todo {summary}"
    else:
        text = summary
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def truncate_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
