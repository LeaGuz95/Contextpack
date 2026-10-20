"""Tests de caracterización para AnalizadorDependencias."""
from pathlib import Path

import pytest


from core.dependencies import AnalizadorDependencias


def escribir(raiz: Path, rel: str, contenido: str) -> Path:
    ruta = raiz / rel
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding='utf-8')
    return ruta


@pytest.fixture
def proyecto(tmp_path):
    """Proyecto mínimo: un paquete Python, JS, Go y C#."""
    escribir(tmp_path, 'app/__init__.py', '')
    escribir(tmp_path, 'app/core.py', (
        'from . import panel\n'
        'from .utils import helper\n'
        'import os\n'
        'from app import models\n'
    ))
    escribir(tmp_path, 'app/panel.py', 'x = 1\n')
    escribir(tmp_path, 'app/utils.py', 'def helper():\n    pass\n')
    escribir(tmp_path, 'app/models.py', 'y = 2\n')
    escribir(tmp_path, 'main.py', 'from app.core import algo\nimport json\n')

    escribir(tmp_path, 'web/index.js', (
        "import { y } from './lib/y';\n"
        "const z = require('./z');\n"
        "import React from 'react';\n"
    ))
    escribir(tmp_path, 'web/lib/y.js', 'export const y = 1;\n')
    escribir(tmp_path, 'web/z.js', 'module.exports = {};\n')

    escribir(tmp_path, 'go.mod', 'module ejemplo.com/mi/app\n')
    escribir(tmp_path, 'cmd/main.go', (
        'package main\n'
        'import (\n'
        '    "fmt"\n'
        '    "ejemplo.com/mi/app/internal/svc"\n'
        ')\n'
    ))
    escribir(tmp_path, 'internal/svc/svc.go', 'package svc\n')
    return tmp_path


def rel(rutas, raiz):
    return sorted(str(r.relative_to(raiz)).replace('\\', '/') for r in rutas)


def orden(rutas, raiz):
    return [str(r.relative_to(raiz)).replace('\\', '/') for r in rutas]


# --- Extracción -------------------------------------------------------------

def test_extrae_imports_de_python(proyecto):
    deps = AnalizadorDependencias.extraer_dependencias(proyecto / 'main.py')
    assert 'app.core' in deps
    assert 'json' in deps


def test_extrae_imports_de_javascript(proyecto):
    deps = AnalizadorDependencias.extraer_dependencias(proyecto / 'web/index.js')
    assert './lib/y' in deps
    assert './z' in deps
    assert 'react' in deps


def test_extrae_imports_de_go(proyecto):
    deps = AnalizadorDependencias.extraer_dependencias(proyecto / 'cmd/main.go')
    assert 'fmt' in deps
    assert 'ejemplo.com/mi/app/internal/svc' in deps


def test_extension_sin_soporte_no_tiene_deps(tmp_path):
    archivo = escribir(tmp_path, 'notas.md', 'import lo_que_sea\n')
    assert AnalizadorDependencias.extraer_dependencias(archivo) == []


# --- Resolución -------------------------------------------------------------

def test_resuelve_python_absoluto(proyecto):
    destino = AnalizadorDependencias.resolver_dependencias(
        'app.core', proyecto / 'main.py', proyecto
    )
    assert rel(destino, proyecto) == ['app/core.py']


def test_resuelve_paquete_a_su_init(proyecto):
    destino = AnalizadorDependencias.resolver_dependencias(
        'app', proyecto / 'main.py', proyecto
    )
    assert rel(destino, proyecto) == ['app/__init__.py']


def test_resuelve_js_relativo(proyecto):
    destino = AnalizadorDependencias.resolver_dependencias(
        './lib/y', proyecto / 'web/index.js', proyecto
    )
    assert rel(destino, proyecto) == ['web/lib/y.js']


def test_descarta_stdlib_python(proyecto):
    assert AnalizadorDependencias.resolver_dependencias(
        'json', proyecto / 'main.py', proyecto
    ) == []


def test_descarta_paquetes_de_terceros_js(proyecto):
    assert AnalizadorDependencias.resolver_dependencias(
        'react', proyecto / 'web/index.js', proyecto
    ) == []


def test_resuelve_import_de_go_por_modulo(proyecto):
    destino = AnalizadorDependencias.resolver_dependencias(
        'ejemplo.com/mi/app/internal/svc', proyecto / 'cmd/main.go', proyecto
    )
    assert rel(destino, proyecto) == ['internal/svc/svc.go']


def test_import_relativo_con_nombre_resuelve_al_modulo(proyecto):
    deps = AnalizadorDependencias.extraer_dependencias(proyecto / 'app/core.py')
    destinos = []
    for dep in deps:
        destinos.extend(
            AnalizadorDependencias.resolver_dependencias(
                dep, proyecto / 'app/core.py', proyecto
            )
        )
    assert 'app/panel.py' in rel(destinos, proyecto)


def test_modulo_del_proyecto_gana_sobre_la_stdlib(tmp_path):
    escribir(tmp_path, 'queue.py', 'q = 1\n')
    origen = escribir(tmp_path, 'uso.py', 'from queue import Empty\n')
    destino = AnalizadorDependencias.resolver_dependencias(
        'queue', origen, tmp_path
    )
    assert rel(destino, tmp_path) == ['queue.py']


# --- Búsqueda recursiva -----------------------------------------------------

def test_relacionados_sigue_la_cadena(proyecto):
    relacionados = AnalizadorDependencias.encontrar_relacionados(
        proyecto / 'main.py', proyecto
    )
    archivos = orden(relacionados, proyecto)
    assert archivos[0] == 'main.py'
    assert 'app/core.py' in archivos
    assert 'app/utils.py' in archivos


def test_relacionados_respeta_profundidad(proyecto):
    # A -> B -> C: con max_prof=0 solo queda el inicial
    escribir(proyecto, 'cadena/a.py', 'import b\n')
    escribir(proyecto, 'cadena/b.py', 'import c\n')
    escribir(proyecto, 'cadena/c.py', 'x = 1\n')
    solo_uno = AnalizadorDependencias.encontrar_relacionados(
        proyecto / 'cadena/a.py', proyecto, max_prof=0
    )
    assert rel(solo_uno, proyecto) == ['cadena/a.py']


def test_relacionados_no_entra_en_ciclos(proyecto):
    escribir(proyecto, 'ciclo/a.js', "import x from './b';\n")
    escribir(proyecto, 'ciclo/b.js', "import y from './a';\n")
    relacionados = AnalizadorDependencias.encontrar_relacionados(
        proyecto / 'ciclo/a.js', proyecto
    )
    archivos = rel(relacionados, proyecto)
    assert archivos.count('ciclo/a.js') == 1
    assert archivos.count('ciclo/b.js') == 1


def test_python_con_error_de_sintaxis_no_rompe_el_analisis(tmp_path):
    archivo = escribir(tmp_path, 'roto.py', 'def (:\n    pass\n')
    assert AnalizadorDependencias.extraer_dependencias(archivo) == []


def test_no_inventa_nombres_importados_como_modulos(tmp_path):
    archivo = escribir(tmp_path, 'uso.py', 'from app import models\n')
    deps = AnalizadorDependencias.extraer_dependencias(archivo)
    assert deps == ['app', 'app.models']


def test_import_relativo_de_dos_niveles(tmp_path):
    escribir(tmp_path, 'pkg/__init__.py', '')
    escribir(tmp_path, 'pkg/base.py', 'x = 1\n')
    origen = escribir(tmp_path, 'pkg/sub/mod.py', 'from .. import base\n')
    destino = AnalizadorDependencias.resolver_dependencias(
        '..base', origen, tmp_path
    )
    assert rel(destino, tmp_path) == ['pkg/base.py']


def test_import_estrella_no_genera_dependencias_falsas(tmp_path):
    archivo = escribir(tmp_path, 'uso.py', 'from paquete import *\n')
    assert AnalizadorDependencias.extraer_dependencias(archivo) == ['paquete']
