#!/usr/bin/env python3
import argparse
import locale
import os
import pathlib
import subprocess
import sys
from typing import Any

from cache import load_cache, save_cache
from cliente_google import get_events
from eventos import details_lines, find_alert_event, list_rows, timed_events
from formatadores import format_event, short_event_text
from notificador import notify_event_if_needed

BASE_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_CREDENTIALS = BASE_DIR / "credentials.json"
DEFAULT_TOKEN = BASE_DIR / "token.json"
DEFAULT_CACHE = BASE_DIR / ".events_cache.json"
DEFAULT_CACHE = BASE_DIR / ".events_cache.json"
DEFAULT_NOTIFY_STATE = BASE_DIR / ".notify_state.json"


def show_popup(lines: list[str]) -> None:
    message = "\n".join(lines) if lines else "Sem eventos nos proximos dias."
    try:
        subprocess.run(["notify-send", "Google Agenda", message], check=False)
    except FileNotFoundError:
        print(message)


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
