import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from xbar_calendar_adapter import event_relevant_today, normalize_event, normalize_events


TODAY = dt.date(2026, 9, 21)


def timed(
    event_id: str,
    start: str,
    end: str,
    summary: str | None = "Evento",
    **extra,
) -> dict:
    event = {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        **extra,
    }
    return event


def all_day(event_id: str, start: str, end: str, summary: str = "Feriado") -> dict:
    return {
        "id": event_id,
        "summary": summary,
        "start": {"date": start},
        "end": {"date": end},
    }


def test_normalizes_timed_event_and_keeps_rfc3339_and_utc() -> None:
    event = normalize_event(
        timed(
            "timed-1",
            "2026-09-21T14:30:00-03:00",
            "2026-09-21T15:00:00-03:00",
        ),
        "primary",
    )

    assert event is not None
    assert event["start"] == "2026-09-21T14:30:00-03:00"
    assert event["end"] == "2026-09-21T15:00:00-03:00"
    assert event["start_utc"] == "2026-09-21T17:30:00Z"
    assert event["end_utc"] == "2026-09-21T18:00:00Z"
    assert event["all_day"] is False


def test_all_day_event_remains_a_calendar_date_in_negative_timezone() -> None:
    event = normalize_event(all_day("all-day-1", "2026-09-21", "2026-09-22"), "primary")

    assert event is not None
    assert event["all_day"] is True
    assert event["start_date"] == "2026-09-21"
    assert event["end_date"] == "2026-09-22"
    assert event["start"] is None
    assert event_relevant_today(event, TODAY)


def test_recurring_occurrence_keeps_both_identity_fields() -> None:
    raw = timed(
        "occurrence-1",
        "2026-09-21T14:30:00-03:00",
        "2026-09-21T15:00:00-03:00",
        recurringEventId="series-1",
        originalStartTime={"dateTime": "2026-09-14T14:30:00-03:00", "timeZone": "America/Sao_Paulo"},
    )

    event = normalize_event(raw, "work")

    assert event is not None
    assert event["recurring_event_id"] == "series-1"
    assert event["original_start_time"]["dateTime"] == "2026-09-14T14:30:00-03:00"
    assert event["original_start_time_utc"] == "2026-09-14T17:30:00Z"


def test_cancelled_status_is_preserved_and_empty_summary_is_explicit() -> None:
    event = normalize_event(
        timed(
            "cancelled-1",
            "2026-09-21T10:00:00-03:00",
            "2026-09-21T10:30:00-03:00",
            summary="",
            status="cancelled",
        ),
        "primary",
    )

    assert event is not None
    assert event["status"] == "cancelled"
    assert event["summary"] == "(Sem titulo)"


def test_today_filter_includes_all_day_timed_and_in_progress_events() -> None:
    events = normalize_events(
        [
            all_day("holiday", "2026-09-21", "2026-09-22"),
            timed("next", "2026-09-21T16:00:00-03:00", "2026-09-21T17:00:00-03:00"),
            timed("spanning", "2026-09-20T23:50:00-03:00", "2026-09-21T00:30:00-03:00"),
            timed("tomorrow", "2026-09-22T09:00:00-03:00", "2026-09-22T10:00:00-03:00"),
        ],
        "primary",
        today=TODAY,
    )

    assert [event["id"] for event in events] == ["holiday", "spanning", "next"]


def test_sort_order_places_all_day_first_then_timed_chronologically() -> None:
    events = normalize_events(
        [
            timed("late", "2026-09-21T18:00:00-03:00", "2026-09-21T19:00:00-03:00"),
            all_day("all-day", "2026-09-21", "2026-09-22"),
            timed("early", "2026-09-21T08:00:00-03:00", "2026-09-21T09:00:00-03:00"),
        ],
        "primary",
    )

    assert [event["id"] for event in events] == ["all-day", "early", "late"]


def test_today_boundary_does_not_include_event_after_local_day() -> None:
    events = normalize_events(
        [
            timed("midnight", "2026-09-22T00:00:00-03:00", "2026-09-22T00:30:00-03:00"),
        ],
        "primary",
        today=TODAY,
    )

    assert events == []
