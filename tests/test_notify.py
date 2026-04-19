import sys
import pathlib
from unittest.mock import patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from notificador import (
    event_key,
    load_notify_state,
    notify_event_if_needed,
    save_notify_state,
)

EVENTO_BASE = {
    "id": "abc123",
    "summary": "Reunião",
    "start": {"dateTime": "2024-06-15T15:00:00+00:00"},
}


class TestNotifyState:
    def test_arquivo_ausente_retorna_dict_vazio(self, tmp_path):
        assert load_notify_state(tmp_path / "nao_existe.json") == {}

    def test_arquivo_corrompido_retorna_dict_vazio(self, tmp_path):
        f = tmp_path / "state.json"
        f.write_text("nao e json", encoding="utf-8")
        assert load_notify_state(f) == {}

    def test_salva_e_recarrega(self, tmp_path):
        f = tmp_path / "state.json"
        save_notify_state(f, {"last_key": "evento:123"})
        result = load_notify_state(f)
        assert result == {"last_key": "evento:123"}

    def test_sobrescreve(self, tmp_path):
        f = tmp_path / "state.json"
        save_notify_state(f, {"last_key": "antigo"})
        save_notify_state(f, {"last_key": "novo"})
        assert load_notify_state(f)["last_key"] == "novo"


class TestEventKey:
    def test_retorna_id_e_datetime(self):
        key = event_key(EVENTO_BASE)
        assert "abc123" in key
        assert "2024-06-15T15:00:00" in key

    def test_evento_sem_id(self):
        key = event_key({"start": {"dateTime": "2024-01-01T00:00:00+00:00"}})
        assert key.startswith(":")

    def test_evento_vazio(self):
        key = event_key({})
        assert key == ":"


class TestNotifyEventIfNeeded:
    def test_envia_notificacao_na_primeira_vez(self, tmp_path):
        f = tmp_path / "state.json"
        with patch("notificador.subprocess.run") as mock_run:
            notify_event_if_needed(EVENTO_BASE, f)
            assert mock_run.called
            args = mock_run.call_args[0][0]
            assert args[0] == "notify-send"

    def test_nao_reenvia_mesma_chave(self, tmp_path):
        f = tmp_path / "state.json"
        key = event_key(EVENTO_BASE)
        save_notify_state(f, {"last_key": key})
        with patch("notificador.subprocess.run") as mock_run:
            notify_event_if_needed(EVENTO_BASE, f)
            assert not mock_run.called

    def test_reenvia_quando_chave_muda(self, tmp_path):
        f = tmp_path / "state.json"
        save_notify_state(f, {"last_key": "outro:evento"})
        with patch("notificador.subprocess.run") as mock_run:
            notify_event_if_needed(EVENTO_BASE, f)
            assert mock_run.called

    def test_persiste_chave_apos_notificar(self, tmp_path):
        f = tmp_path / "state.json"
        with patch("notificador.subprocess.run"):
            notify_event_if_needed(EVENTO_BASE, f)
        state = load_notify_state(f)
        assert state["last_key"] == event_key(EVENTO_BASE)
