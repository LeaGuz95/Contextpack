"""Fixtures compartidas: proyectos de prueba y el modelo de vista sin Qt."""
from pathlib import Path

import pytest

from core import ConfigManager
from core.context import ConstructorContexto
from models.data_models import InfoArchivo, ResultadoEscaneo
from ui.model_view import ModeloVista


def escribir(base: Path, rel: str, contenido: str) -> Path:
    ruta = base / rel
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding='utf-8')
    return ruta


def _nodo(raiz: dict, partes) -> dict:
    nivel = raiz
    for parte in partes:
        nivel = nivel.setdefault(parte, {})
    return nivel


def construir_resultado(base: Path, archivos: dict) -> ResultadoEscaneo:
    """Arma un ResultadoEscaneo con el árbol que devolvería el escáner."""
    infos = []
    arbol = {'.': {}}

    for rel, contenido in archivos.items():
        ruta = escribir(base, rel, contenido)
        infos.append(InfoArchivo(
            ruta=ruta,
            ruta_relativa=str(Path(rel)),
            lineas=len(contenido.splitlines()),
            tamano_bytes=len(contenido.encode('utf-8')),
        ))
        partes = Path(rel).parts
        _nodo(arbol['.'], partes[:-1])[partes[-1]] = None

    return ResultadoEscaneo(
        ruta_raiz=base,
        archivos=infos,
        cantidad_ignorados=0,
        total_lineas=sum(i.lineas for i in infos),
        arbol_directorios=arbol,
    )


@pytest.fixture
def resultado(tmp_path):
    return construir_resultado(tmp_path, {
        'main.py': 'import os\n\nprint("hola")\n',
        'core/utils.py': 'def suma(a, b):\n    return a + b\n',
        'core/config.py': 'API_KEY = "sk-test-1234567890"\n',
        'docs/README.md': '# Título\n\nTexto.\n',
    })


@pytest.fixture
def constructor():
    return ConstructorContexto()


@pytest.fixture
def modelo(tmp_path, monkeypatch):
    """ModeloVista con una configuración propia, sin tocar la del usuario."""
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    return ModeloVista(ConfigManager())


@pytest.fixture
def modelo_con_proyecto(modelo, resultado):
    modelo.establecer_resultado(resultado)
    return modelo
