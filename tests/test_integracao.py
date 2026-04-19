"""
Testes de integração: executa google_agenda_polybar.py como subprocess com
Google API mockada, sem credenciais reais.
"""
import datetime as dt
import json
import pathlib
import runpy
import subprocess
import sys
import time

import pytest

SCRIPT = str(pathlib.Path(__file__).resolve().parent.parent / "google_agenda_polybar.py")
STUBS_DIR = pathlib.Path(__file__).resolve().parent / "stubs_integracao"


@pytest.fixture(autouse=True, scope="session")
def criar_stubs(tmp_path_factory):
    """Cria stubs da Google API e credentials falsos para os testes."""
    stubs = tmp_path_factory.mktemp("stubs")

    # credentials.json falso (apenas para passar na checagem de existência)
    creds = {
        "installed": {
            "client_id": "fake.apps.googleusercontent.com",
            "client_secret": "fake_secret",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    (stubs / "credentials.json").write_text(json.dumps(creds), encoding="utf-8")

    return stubs


def _run_mode(mode: str, extra_args: list, stubs: pathlib.Path, cache: pathlib.Path) -> subprocess.CompletedProcess:
    """Executa o script em um modo com cache pré-populado."""
    return subprocess.run(
        [
            sys.executable, SCRIPT,
            "--mode", mode,
            "--credentials", str(stubs / "credentials.json"),
            "--token", str(stubs / "token_fake.json"),
            "--cache-file", str(cache),
            "--notify-state-file", str(stubs / "notify_state.json"),
            *extra_args,
        ],
        capture_output=True,
        text=True,
    )


def _populate_cache(cache_file: pathlib.Path, events: list) -> None:
    payload = {"timestamp": time.time(), "events": events}
    cache_file.write_text(json.dumps(payload), encoding="utf-8")


def _evento_com_horario(summary: str, offset_minutes: int = 120) -> dict:
    start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=offset_minutes)
    return {
        "id": summary,
        "summary": summary,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": (start + dt.timedelta(hours=1)).isoformat()},
    }


def _evento_dia_todo(summary: str, days_ahead: int = 1) -> dict:
    target = (dt.datetime.now().date() + dt.timedelta(days=days_ahead)).isoformat()
    return {
        "id": summary,
        "summary": summary,
        "start": {"date": target},
        "end": {"date": target},
    }


class TestModoModule:
    def test_sem_evento_proximo_imprime_icone(self, criar_stubs, tmp_path):
        cache = tmp_path / "cache.json"
        _populate_cache(cache, [_evento_com_horario("Futuro", offset_minutes=120)])
        result = _run_mode("module", [], criar_stubs, cache)
        assert result.returncode == 0
        assert "" in result.stdout

    def test_com_evento_proximo_imprime_icone_e_texto(self, criar_stubs, tmp_path):
        cache = tmp_path / "cache.json"
        _populate_cache(cache, [_evento_com_horario("Stand-up", offset_minutes=5)])
        result = _run_mode("module", ["--alert-minutes", "10"], criar_stubs, cache)
        assert result.returncode == 0
        assert "" in result.stdout
        assert "Stand-up" in result.stdout

    def test_sem_credentials_imprime_mensagem(self, tmp_path):
        cache = tmp_path / "cache.json"
        stubs = tmp_path / "stubs_sem_creds"
        stubs.mkdir()
        result = subprocess.run(
            [sys.executable, SCRIPT, "--mode", "module",
             "--credentials", str(stubs / "nao_existe.json"),
             "--cache-file", str(cache)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "sem credentials" in result.stdout


class TestModoPrint:
    def test_imprime_eventos_com_horario(self, criar_stubs, tmp_path):
        cache = tmp_path / "cache.json"
        _populate_cache(cache, [
            _evento_com_horario("Reunião"),
            _evento_dia_todo("Feriado"),
        ])
        result = _run_mode("print", [], criar_stubs, cache)
        assert result.returncode == 0
        assert "Reunião" in result.stdout

    def test_sem_eventos_imprime_mensagem(self, criar_stubs, tmp_path):
        cache = tmp_path / "cache.json"
        _populate_cache(cache, [])
        result = _run_mode("print", [], criar_stubs, cache)
        assert result.returncode == 0
        assert "Sem eventos" in result.stdout


class TestModoDetails:
    def test_imprime_eventos_agrupados(self, criar_stubs, tmp_path):
        cache = tmp_path / "cache.json"
        _populate_cache(cache, [_evento_com_horario("Daily", 60)])
        result = _run_mode("details", [], criar_stubs, cache)
        assert result.returncode == 0
        assert "Daily" in result.stdout

    def test_sem_eventos_nada_imprime(self, criar_stubs, tmp_path):
        cache = tmp_path / "cache.json"
        _populate_cache(cache, [])
        result = _run_mode("details", [], criar_stubs, cache)
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestModoList7:
    def test_imprime_linhas_tab_separadas(self, criar_stubs, tmp_path):
        cache = tmp_path / "cache.json"
        _populate_cache(cache, [_evento_com_horario("Sprint review", 60)])
        result = _run_mode("list7", [], criar_stubs, cache)
        assert result.returncode == 0
        assert "\t" in result.stdout
        assert "Sprint review" in result.stdout

    def test_sem_eventos_nada_imprime(self, criar_stubs, tmp_path):
        cache = tmp_path / "cache.json"
        _populate_cache(cache, [])
        result = _run_mode("list7", [], criar_stubs, cache)
        assert result.returncode == 0
        assert result.stdout.strip() == ""
