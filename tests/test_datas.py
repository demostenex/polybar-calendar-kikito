import datetime as dt
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from formatadores import (
    end_of_local_day_iso,
    format_event,
    parse_date,
    short_event_text,
    truncate_text,
)


class TestParseDate:
    def test_datetime_iso(self):
        result = parse_date("2024-06-15T14:30:00+00:00")
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30

    def test_datetime_com_z(self):
        result = parse_date("2024-06-15T14:30:00Z")
        assert result.tzinfo is not None
        assert result.hour == 14

    def test_date_apenas_dia(self):
        result = parse_date("2024-06-15")
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15
        assert result.tzinfo == dt.timezone.utc

    def test_preserva_timezone(self):
        result = parse_date("2024-06-15T14:30:00-03:00")
        assert result.utcoffset() == dt.timedelta(hours=-3)


class TestFormatEvent:
    def test_evento_com_horario(self):
        event = {"start": {"dateTime": "2024-06-15T14:30:00+00:00"}, "summary": "Reunião"}
        result = format_event(event)
        assert "Reunião" in result
        assert "/" in result

    def test_evento_dia_todo(self):
        event = {"start": {"date": "2024-06-15"}, "summary": "Feriado"}
        result = format_event(event)
        assert "Feriado" in result
        assert "dia todo" in result

    def test_evento_sem_summary(self):
        event = {"start": {"dateTime": "2024-06-15T10:00:00+00:00"}}
        result = format_event(event)
        assert "(Sem titulo)" in result

    def test_evento_sem_start(self):
        event = {"summary": "Algo"}
        result = format_event(event)
        assert result == "Algo"


class TestShortEventText:
    def test_texto_curto_nao_trunca(self):
        event = {"start": {"dateTime": "2024-06-15T09:00:00+00:00"}, "summary": "Stand-up"}
        result = short_event_text(event, max_len=36)
        assert "Stand-up" in result
        assert len(result) <= 36

    def test_texto_longo_trunca(self):
        event = {
            "start": {"dateTime": "2024-06-15T09:00:00+00:00"},
            "summary": "Reunião muito longa com título gigante que não cabe",
        }
        result = short_event_text(event, max_len=20)
        assert len(result) == 20
        assert result.endswith("…")

    def test_evento_dia_todo(self):
        event = {"start": {"date": "2024-06-15"}, "summary": "Natal"}
        result = short_event_text(event)
        assert "dia todo" in result
        assert "Natal" in result

    def test_evento_sem_start(self):
        event = {"summary": "Algo"}
        result = short_event_text(event)
        assert result == "Algo"


class TestTruncateText:
    def test_texto_dentro_do_limite(self):
        assert truncate_text("abc", 10) == "abc"

    def test_texto_no_limite_exato(self):
        assert truncate_text("abcde", 5) == "abcde"

    def test_texto_acima_do_limite(self):
        result = truncate_text("abcdefgh", 5)
        assert len(result) == 5
        assert result.endswith("…")

    def test_limite_1(self):
        result = truncate_text("abc", 1)
        assert result == "…"


class TestEndOfLocalDayIso:
    def test_retorna_string_iso(self):
        result = end_of_local_day_iso(0)
        assert "T23:59:59" in result

    def test_amanha(self):
        hoje = dt.datetime.now().astimezone().date()
        amanha = hoje + dt.timedelta(days=1)
        result = end_of_local_day_iso(1)
        assert str(amanha) in result
