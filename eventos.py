import datetime as dt
from typing import Any

from formatadores import parse_date, truncate_text


def timed_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if "dateTime" in event.get("start", {})]


def minutes_until(event: dict[str, Any], now: dt.datetime) -> int:
    start = parse_date(event["start"]["dateTime"]).astimezone()
    return int((start - now).total_seconds() // 60)


def find_alert_event(events: list[dict[str, Any]], alert_minutes: int) -> dict[str, Any] | None:
    now = dt.datetime.now().astimezone()
    for event in timed_events(events):
        mins = minutes_until(event, now)
        if 0 <= mins <= alert_minutes:
            return event
    return None


def details_lines(events: list[dict[str, Any]], date_format: str) -> list[str]:
    grouped: dict[str, tuple[dt.datetime, list[str]]] = {}
    for event in events:
        start_data = event.get("start", {})
        summary = event.get("summary", "(Sem titulo)")
        if "dateTime" in start_data:
            start = parse_date(start_data["dateTime"]).astimezone()
            day_key = start.strftime(date_format)
            desc = f"{start:%H:%M} - {summary}"
        elif "date" in start_data:
            start = parse_date(start_data["date"]).astimezone()
            day_key = start.strftime(date_format)
            desc = f"(dia todo) - {summary}"
        else:
            continue
        day_start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        if day_key not in grouped:
            grouped[day_key] = (day_start, [desc])
        else:
            grouped[day_key][1].append(desc)

    ordered = sorted(grouped.items(), key=lambda item: item[1][0])
    return [f"{day_key} {' | '.join(descs)}" for day_key, (_, descs) in ordered]


def list_rows(events: list[dict[str, Any]], max_desc_len: int) -> list[tuple[str, str, str]]:
    rows: list[tuple[dt.datetime, str, str, str]] = []
    for event in events:
        start_data = event.get("start", {})
        summary = event.get("summary", "(Sem titulo)")
        if "dateTime" in start_data:
            start = parse_date(start_data["dateTime"]).astimezone()
            full_desc = f"{start:%H:%M} - {summary}"
            rows.append((start, f"{start:%d/%m}", truncate_text(full_desc, max_desc_len), full_desc))
        elif "date" in start_data:
            start = parse_date(start_data["date"]).astimezone()
            full_desc = f"(dia todo) - {summary}"
            rows.append((start, f"{start:%d/%m}", truncate_text(full_desc, max_desc_len), full_desc))
    rows.sort(key=lambda item: item[0])
    return [(date, desc, full_desc) for _, date, desc, full_desc in rows]
