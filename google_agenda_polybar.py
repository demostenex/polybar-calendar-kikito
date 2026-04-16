#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import locale
import os
import pathlib
import subprocess
import sys
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
BASE_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_CREDENTIALS = BASE_DIR / "credentials.json"
DEFAULT_TOKEN = BASE_DIR / "token.json"
DEFAULT_CACHE = BASE_DIR / ".events_cache.json"
DEFAULT_NOTIFY_STATE = BASE_DIR / ".notify_state.json"


def now_utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


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
    now = dt.datetime.now().astimezone()
    mins = max(0, int((start - now).total_seconds() // 60))
    summary = event.get("summary", "(Sem titulo)")
    body = f"{start:%H:%M} - {summary}"
    subprocess.run(["notify-send", f"Agenda em {mins} min", body], check=False)
    save_notify_state(state_file, {"last_key": key})


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


def build_service(credentials_file: pathlib.Path, token_file: pathlib.Path, open_browser: bool):
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
            creds = flow.run_local_server(
                port=0,
                redirect_uri_trailing_slash=False,
                open_browser=open_browser,
            )
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds)


def fetch_events(
    credentials_file: pathlib.Path,
    token_file: pathlib.Path,
    calendar_id: str,
    days: int,
    limit: int,
    open_browser: bool,
) -> list[dict[str, Any]]:
    service = build_service(credentials_file, token_file, open_browser=open_browser)
    time_min = now_utc_iso()
    time_max = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)).isoformat()
    collected: list[dict[str, Any]] = []
    next_page_token: str | None = None
    page_size = 2500

    while True:
        max_results = page_size if limit <= 0 else min(page_size, max(1, limit - len(collected)))
        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
                pageToken=next_page_token,
            )
            .execute()
        )
        collected.extend(result.get("items", []))
        if limit > 0 and len(collected) >= limit:
            return collected[:limit]
        next_page_token = result.get("nextPageToken")
        if not next_page_token:
            return collected


def get_events(
    credentials_file: pathlib.Path,
    token_file: pathlib.Path,
    cache_file: pathlib.Path,
    calendar_id: str,
    days: int,
    limit: int,
    ttl: int,
    open_browser: bool,
) -> list[dict[str, Any]]:
    cached = load_cache(cache_file, ttl)
    if cached is not None:
        return cached
    events = fetch_events(
        credentials_file, token_file, calendar_id, days, limit, open_browser=open_browser
    )
    save_cache(cache_file, events)
    return events


def show_popup(lines: list[str]) -> None:
    message = "\n".join(lines) if lines else "Sem eventos nos proximos dias."
    try:
        subprocess.run(["notify-send", "Google Agenda", message], check=False)
    except FileNotFoundError:
        print(message)


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


def main() -> int:
    try:
        locale.setlocale(locale.LC_TIME, "")
    except locale.Error:
        pass

    parser = argparse.ArgumentParser(description="Google Calendar para Polybar")
    parser.add_argument(
        "--mode", choices=["module", "popup", "print", "details", "list7"], default="module"
    )
    parser.add_argument("--calendar-id", default=os.getenv("GCAL_CALENDAR_ID", "primary"))
    parser.add_argument("--credentials", default=str(DEFAULT_CREDENTIALS))
    parser.add_argument("--token", default=str(DEFAULT_TOKEN))
    parser.add_argument("--cache-file", default=str(DEFAULT_CACHE))
    parser.add_argument("--notify-state-file", default=str(DEFAULT_NOTIFY_STATE))
    parser.add_argument("--cache-ttl", type=int, default=300)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--alert-minutes", type=int, default=10)
    parser.add_argument("--details-date-format", default="%x")
    parser.add_argument("--list-max-len", type=int, default=30)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    credentials_file = pathlib.Path(args.credentials).expanduser().resolve()
    token_file = pathlib.Path(args.token).expanduser().resolve()
    cache_file = pathlib.Path(args.cache_file).expanduser().resolve()
    notify_state_file = pathlib.Path(args.notify_state_file).expanduser().resolve()

    if not credentials_file.exists():
        if args.mode == "module":
            print(" sem credentials")
            return 0
        print(f"Arquivo nao encontrado: {credentials_file}", file=sys.stderr)
        return 1

    try:
        events = get_events(
            credentials_file=credentials_file,
            token_file=token_file,
            cache_file=cache_file,
            calendar_id=args.calendar_id,
            days=args.days,
            limit=args.limit,
            ttl=args.cache_ttl,
            open_browser=not args.no_browser,
        )
    except Exception as exc:
        if args.mode == "module":
            print(" erro agenda")
            return 0
        print(f"Erro ao buscar eventos: {exc}", file=sys.stderr)
        return 1

    timed = timed_events(events)
    lines = [format_event(event) for event in timed]

    if args.mode == "popup":
        show_popup(lines)
        return 0
    if args.mode == "print":
        if lines:
            print("\n".join(lines))
        else:
            print("Sem eventos com horario nos proximos dias.")
        return 0
    if args.mode == "details":
        details = details_lines(events, args.details_date_format)
        if details:
            print("\n".join(details))
        return 0
    if args.mode == "list7":
        rows = list_rows(events, max_desc_len=args.list_max_len)
        if rows:
            print("\n".join(f"{date}\t{desc}\t{full_desc}" for date, desc, full_desc in rows))
        return 0

    alert_event = find_alert_event(events, args.alert_minutes)
    if not alert_event:
        print("")
        return 0

    notify_event_if_needed(alert_event, notify_state_file)
    print(f" {short_event_text(alert_event)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
