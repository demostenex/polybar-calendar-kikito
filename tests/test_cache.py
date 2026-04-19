import json
import sys
import pathlib
import time

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from cache import load_cache, save_cache


class TestLoadCache:
    def test_arquivo_ausente_retorna_none(self, tmp_path):
        assert load_cache(tmp_path / "nao_existe.json", ttl=300) is None

    def test_arquivo_corrompido_retorna_none(self, tmp_path):
        f = tmp_path / "cache.json"
        f.write_text("{ isso nao e json }", encoding="utf-8")
        assert load_cache(f, ttl=300) is None

    def test_cache_valido_retorna_eventos(self, tmp_path):
        f = tmp_path / "cache.json"
        eventos = [{"summary": "Evento 1"}, {"summary": "Evento 2"}]
        save_cache(f, eventos)
        result = load_cache(f, ttl=300)
        assert result == eventos

    def test_cache_expirado_retorna_none(self, tmp_path):
        f = tmp_path / "cache.json"
        eventos = [{"summary": "Velho"}]
        payload = {"timestamp": time.time() - 400, "events": eventos}
        f.write_text(json.dumps(payload), encoding="utf-8")
        assert load_cache(f, ttl=300) is None

    def test_cache_sem_timestamp_retorna_none(self, tmp_path):
        f = tmp_path / "cache.json"
        f.write_text(json.dumps({"events": []}), encoding="utf-8")
        assert load_cache(f, ttl=300) is None

    def test_cache_sem_events_retorna_none(self, tmp_path):
        f = tmp_path / "cache.json"
        f.write_text(json.dumps({"timestamp": time.time()}), encoding="utf-8")
        assert load_cache(f, ttl=300) is None


class TestSaveCache:
    def test_salva_e_recarrega(self, tmp_path):
        f = tmp_path / "cache.json"
        eventos = [{"id": "1", "summary": "Evento"}]
        save_cache(f, eventos)
        assert f.exists()
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data["events"] == eventos
        assert isinstance(data["timestamp"], float)

    def test_sobrescreve_cache_anterior(self, tmp_path):
        f = tmp_path / "cache.json"
        save_cache(f, [{"summary": "Primeiro"}])
        save_cache(f, [{"summary": "Segundo"}])
        result = load_cache(f, ttl=300)
        assert result == [{"summary": "Segundo"}]
