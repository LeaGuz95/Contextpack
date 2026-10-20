"""Tests de ConfigManager: guardado atómico, respaldo y `establecer`."""
import json
from pathlib import Path

from core import ConfigManager


def nuevo_config(tmp_path, monkeypatch) -> ConfigManager:
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    return ConfigManager()


def test_config_nuevo_usa_los_valores_por_defecto(tmp_path, monkeypatch):
    config = nuevo_config(tmp_path, monkeypatch)
    assert config.config['quitar_comentarios'] is False
    assert config.config['perfiles'] == {}


def test_guardar_y_releer(tmp_path, monkeypatch):
    config = nuevo_config(tmp_path, monkeypatch)
    config.establecer(modelo_objetivo='GPT-4o', tamano_max_kb=256)

    otro = nuevo_config(tmp_path, monkeypatch)
    assert otro.config['modelo_objetivo'] == 'GPT-4o'
    assert otro.config['tamano_max_kb'] == 256


def test_guardar_no_deja_el_temporal(tmp_path, monkeypatch):
    config = nuevo_config(tmp_path, monkeypatch)
    config.establecer(ultima_carpeta=str(tmp_path))

    carpeta = config.config_path.parent
    assert not list(carpeta.glob('config.json.*'))


def test_un_error_al_guardar_no_toca_el_archivo_bueno(tmp_path, monkeypatch):
    config = nuevo_config(tmp_path, monkeypatch)
    config.establecer(modelo_objetivo='bueno')

    config.config['inservible'] = {1, 2, 3}   # no es serializable
    config.guardar()

    guardado = json.loads(config.config_path.read_text(encoding='utf-8'))
    assert guardado['modelo_objetivo'] == 'bueno'
    assert 'inservible' not in guardado
    assert not list(config.config_path.parent.glob('config.json.tmp'))


def test_guardar_una_sola_vez_con_establecer(tmp_path, monkeypatch):
    config = nuevo_config(tmp_path, monkeypatch)
    llamadas = []
    original = config.guardar

    def contar():
        llamadas.append(1)
        original()

    monkeypatch.setattr(config, 'guardar', contar)
    config.establecer(a=1, b=2)

    assert len(llamadas) == 1
    assert config.config['a'] == 1 and config.config['b'] == 2


def test_config_ilegible_se_respalda_y_no_se_pisa(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    carpeta = tmp_path / '.contextpack'
    carpeta.mkdir()
    roto = carpeta / 'config.json'
    roto.write_text('{ esto no es json', encoding='utf-8')

    config = ConfigManager()
    assert config.config['perfiles'] == {}

    respaldo = carpeta / 'config.json.ilegible'
    assert respaldo.exists()
    assert respaldo.read_text(encoding='utf-8') == '{ esto no es json'

    # El primer guardado escribe un config válido y no toca el respaldo
    config.establecer(ultima_carpeta=str(tmp_path))
    assert json.loads(roto.read_text(encoding='utf-8'))['ultima_carpeta']
    assert respaldo.read_text(encoding='utf-8') == '{ esto no es json'


def test_faltan_claves_de_una_version_vieja(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    carpeta = tmp_path / '.contextpack'
    carpeta.mkdir()
    (carpeta / 'config.json').write_text('{"modelo_objetivo": "viejo"}', encoding='utf-8')

    config = ConfigManager()
    assert config.config['modelo_objetivo'] == 'viejo'
    assert config.config['ventana_ancho'] == 1200
