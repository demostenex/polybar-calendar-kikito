import pathlib
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from cache import load_cache, save_cache
from formatadores import now_utc_iso, end_of_local_day_iso

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


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
    time_max = end_of_local_day_iso(days)
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
