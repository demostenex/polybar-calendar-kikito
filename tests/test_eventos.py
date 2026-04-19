import datetime as dt
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from eventos import (
    details_lines,
    find_alert_event,
    list_rows,
    minutes_until,
    timed_events,
)


def make_timed(summary: str, offset_minutes: int = 60) -> dict:
    """Cria evento com horário relativo a agora."""
    start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=offset_minutes)
    return {"id": summary, "summary": summary, "start": {"dateTime": start.isoformat()}}


def make_allday(summary: str, days_ahead: int = 1) -> dict:
    target = (dt.datetime.now().date() + dt.timedelta(days=days_ahead)).isoformat()
    return {"id": summary, "summary": summary, "start": {"date": target}}


class TestTimedEvents:
    def test_filtra_apenas_com_horario(self):
        events = [make_timed("A"), make_allday("B"), make_timed("C")]
        result = timed_events(events)
        assert len(result) == 2
        assert all("dateTime" in e["start"] for e in result)

    def test_lista_vazia(self):
        assert timed_events([]) == []

    def test_todos_dia_todo(self):
        assert timed_events([make_allday("X"), make_allday("Y")]) == []


class TestMinutesUntil:
    def test_evento_no_futuro(self):
        event = make_timed("A", offset_minutes=30)
        now = dt.datetime.now().astimezone()
        mins = minutes_until(event, now)
        assert 28 <= mins <= 31

    def test_evento_imediato(self):
        event = make_timed("B", offset_minutes=0)
        now = dt.datetime.now().astimezone()
        mins = minutes_until(event, now)
        assert -2 <= mins <= 2


class TestFindAlertEvent:
    def test_encontra_evento_dentro_do_alert(self):
        event = make_timed("Urgente", offset_minutes=5)
        result = find_alert_event([event], alert_minutes=10)
        assert result is not None
        assert result["summary"] == "Urgente"

    def test_nao_encontra_evento_fora_do_alert(self):
        event = make_timed("Longe", offset_minutes=60)
        result = find_alert_event([event], alert_minutes=10)
        assert result is None

    def test_nao_encontra_evento_passado(self):
        event = make_timed("Passado", offset_minutes=-5)
        result = find_alert_event([event], alert_minutes=10)
        assert result is None

    def test_lista_vazia(self):
        assert find_alert_event([], alert_minutes=10) is None

    def test_dia_todo_nao_conta(self):
        event = make_allday("Feriado")
        assert find_alert_event([event], alert_minutes=10) is None


class TestDetailsLines:
    def test_agrupa_por_dia(self):
        events = [
            make_timed("Reunião A", 60),
            make_timed("Reunião B", 90),
            make_allday("Feriado"),
        ]
        lines = details_lines(events, date_format="%Y-%m-%d")
        assert len(lines) >= 1
        for line in lines:
            assert " | " in line or "-" in line

    def test_lista_vazia_retorna_vazio(self):
        assert details_lines([], date_format="%Y-%m-%d") == []

    def test_evento_sem_start_ignorado(self):
        events = [{"summary": "Sem data"}]
        assert details_lines(events, date_format="%Y-%m-%d") == []


class TestListRows:
    def test_retorna_tuplas_com_tres_colunas(self):
        events = [make_timed("Evento X", 60), make_allday("Dia todo Y")]
        rows = list_rows(events, max_desc_len=30)
        assert len(rows) == 2
        for row in rows:
            assert len(row) == 3

    def test_ordenado_por_horario(self):
        e1 = make_timed("Tarde", 120)
        e2 = make_timed("Cedo", 30)
        rows = list_rows([e1, e2], max_desc_len=30)
        # full_desc (col 3) contém o summary sem truncar — verifica ordem cronológica
        assert "Cedo" in rows[0][2] and "Tarde" in rows[1][2]

    def test_desc_truncada(self):
        summary = "Evento com titulo muito longo mesmo"
        events = [make_timed(summary, 60)]
        rows = list_rows(events, max_desc_len=10)
        assert len(rows[0][1]) == 10
        assert rows[0][1].endswith("…")

    def test_lista_vazia(self):
        assert list_rows([], max_desc_len=30) == []
