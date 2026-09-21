#!/usr/bin/env python3
"""Structured, machine-readable Google Calendar data for a future xbar sensor."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
from typing import Any


BASE_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_CREDENTIALS = BASE_DIR / "credentials.json"
DEFAULT_TOKEN = BASE_DIR / "token.json"
DEFAULT_CACHE_TODAY = BASE_DIR / ".xbar_calendar_today_cache.json"
DEFAULT_CACHE_WINDOW = BASE_DIR / ".xbar_calendar_window_cache.json"


def parse_rfc3339(value: str) -> dt.datetime:
    """Parse a Google dateTime while requiring an explicit timezone offset."""
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timed event has no timezone offset: {value!r}")
    return parsed


def utc_iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def local_timezone_name(now: dt.datetime) -> str:
    zone = getattr(now.tzinfo, "key", None)
    return zone or now.tzname() or "local"


def _original_start_time(event: dict[str, Any]) -> tuple[Any, str | None]:
    original = event.get("originalStartTime")
    if not isinstance(original, dict):
        return None, None
    value = original.get("dateTime")
    if isinstance(value, str):
        return original, utc_iso(parse_rfc3339(value))
    return original, None


def normalize_event(event: dict[str, Any], calendar_id: str) -> dict[str, Any] | None:
    start_data = event.get("start")
    end_data = event.get("end")
    if not isinstance(start_data, dict) or not isinstance(end_data, dict):
        return None

    original_start_time, original_start_time_utc = _original_start_time(event)
    start_date_time = start_data.get("dateTime")
    end_date_time = end_data.get("dateTime")
    summary = event.get("summary") or "(Sem titulo)"
    status = event.get("status") or "confirmed"

    if isinstance(start_date_time, str) and isinstance(end_date_time, str):
        start = parse_rfc3339(start_date_time)
        end = parse_rfc3339(end_date_time)
        return {
            "calendar_id": calendar_id,
            "id": event.get("id"),
            "recurring_event_id": event.get("recurringEventId"),
            "original_start_time": original_start_time,
            "original_start_time_utc": original_start_time_utc,
            "summary": str(summary),
            "start": start_date_time,
            "end": end_date_time,
            "start_utc": utc_iso(start),
            "end_utc": utc_iso(end),
            "timezone": start_data.get("timeZone") or end_data.get("timeZone"),
            "start_date": None,
            "end_date": None,
            "all_day": False,
            "status": str(status),
        }

    start_date = start_data.get("date")
    end_date = end_data.get("date")
    if isinstance(start_date, str) and isinstance(end_date, str):
        # Google dates are calendar dates. They are deliberately not converted
        # through UTC or astimezone(), which would shift dates in negative TZs.
        return {
            "calendar_id": calendar_id,
            "id": event.get("id"),
            "recurring_event_id": event.get("recurringEventId"),
            "original_start_time": original_start_time,
            "original_start_time_utc": original_start_time_utc,
            "summary": str(summary),
            "start": None,
            "end": None,
            "start_utc": None,
            "end_utc": None,
            "timezone": start_data.get("timeZone") or end_data.get("timeZone"),
            "start_date": start_date,
            "end_date": end_date,
            "all_day": True,
            "status": str(status),
        }

    return None


def event_relevant_today(event: dict[str, Any], today: dt.date) -> bool:
    if event["all_day"]:
        return event["start_date"] <= today.isoformat() < event["end_date"]

    start = parse_rfc3339(event["start"])
    end = parse_rfc3339(event["end"])
    day_start = dt.datetime.combine(today, dt.time.min, tzinfo=start.astimezone().tzinfo)
    day_end = day_start + dt.timedelta(days=1)
    return start < day_end.astimezone(start.tzinfo) and end > day_start.astimezone(end.tzinfo)


def sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(event: dict[str, Any]) -> tuple[int, str]:
        if event["all_day"]:
            return (0, event["start_date"])
        return (1, event["start_utc"])

    return sorted(events, key=key)


def normalize_events(
    raw_events: list[dict[str, Any]], calendar_id: str, today: dt.date | None = None
) -> list[dict[str, Any]]:
    normalized = [
        normalized
        for raw in raw_events
        if (normalized := normalize_event(raw, calendar_id)) is not None
    ]
    if today is not None:
        normalized = [event for event in normalized if event_relevant_today(event, today)]
    return sort_events(normalized)


def local_day_bounds(now: dt.datetime) -> tuple[str, str]:
    local_midnight = dt.datetime.combine(now.date(), dt.time.min, tzinfo=now.tzinfo)
    next_midnight = local_midnight + dt.timedelta(days=1)
    return utc_iso(local_midnight), utc_iso(next_midnight)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Structured Google Calendar JSON adapter")
    subparsers = parser.add_subparsers(dest="command", required=True)

    today = subparsers.add_parser("today", help="events relevant to the current local date")
    today.set_defaults(days=0)

    window = subparsers.add_parser("window", help="events in a future window")
    window.add_argument("--days", type=int, default=7)

    common = (
        ("--calendar-id", {"default": os.getenv("GCAL_CALENDAR_ID", "primary")}),
        ("--credentials", {"default": str(DEFAULT_CREDENTIALS)}),
        ("--token", {"default": str(DEFAULT_TOKEN)}),
        ("--cache-ttl", {"type": int, "default": 300}),
        ("--cache-file", {}),
        ("--limit", {"type": int, "default": 0}),
        ("--no-browser", {"action": "store_true"}),
    )
    for option, kwargs in common:
        parser.add_argument(option, **kwargs)
        sub_kwargs = dict(kwargs)
        sub_kwargs["default"] = argparse.SUPPRESS
        today.add_argument(option, **sub_kwargs)
        window.add_argument(option, **sub_kwargs)
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    now = dt.datetime.now().astimezone()
    credentials_file = pathlib.Path(args.credentials).expanduser().resolve()
    token_file = pathlib.Path(args.token).expanduser().resolve()
    if not credentials_file.exists():
        raise FileNotFoundError(f"credentials file not found: {credentials_file}")

    # Imported lazily so normalization tests do not require OAuth dependencies.
    from cliente_google import get_events

    if args.cache_file:
        cache_file = pathlib.Path(args.cache_file).expanduser().resolve()
    elif args.command == "today":
        cache_file = DEFAULT_CACHE_TODAY
    else:
        cache_file = DEFAULT_CACHE_WINDOW

    if args.command == "today":
        time_min, time_max = local_day_bounds(now)
        raw_events = get_events(
            credentials_file,
            token_file,
            cache_file,
            args.calendar_id,
            days=0,
            limit=args.limit,
            ttl=args.cache_ttl,
            open_browser=not args.no_browser,
            time_min=time_min,
            time_max=time_max,
        )
        events = normalize_events(raw_events, args.calendar_id, today=now.date())
        mode = "today"
    else:
        if args.days < 0:
            raise ValueError("--days must be non-negative")
        raw_events = get_events(
            credentials_file,
            token_file,
            args.calendar_id,
            days=args.days,
            limit=args.limit,
            ttl=args.cache_ttl,
            open_browser=not args.no_browser,
        )
        events = normalize_events(raw_events, args.calendar_id)
        mode = "window"

    return {
        "generated_at": utc_iso(dt.datetime.now(dt.timezone.utc)),
        "timezone": local_timezone_name(now),
        "local_date": now.date().isoformat(),
        "mode": mode,
        "events": events,
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        document = run(args)
    except Exception as exc:
        print(f"calendar adapter error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(document, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
