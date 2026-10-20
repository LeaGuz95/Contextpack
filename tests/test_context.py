"""Tests de ConstructorContexto: formato, redacción y caché por archivo."""
import os
from pathlib import Path

from core import OpcionesOptimizacion
from core.context import ConstructorContexto


def test_construir_incluye_todos_los_archivos(constructor, resultado):
    texto = constructor.construir(resultado)
    for info in resultado.archivos:
        assert info.ruta_relativa in texto
    assert '===== CONTEXTO DEL PROYECTO =====' in texto


def test_construir_markdown_usa_fences_por_lenguaje(constructor, resultado):
    texto = constructor.construir_markdown(resultado)
    assert '```python' in texto
    assert '```markdown' in texto
    assert '## ARCHIVO: main.py' in texto


def test_markdown_incluye_la_plantilla(constructor, resultado):
    constructor.establecer_plantilla('Respondé en castellano.')
    texto = constructor.construir_markdown(resultado)
    assert texto.startswith('# INSTRUCCIONES')
    assert 'Respondé en castellano.' in texto


def test_ambos_formatos_redactan_igual(constructor, resultado):
    txt = constructor.construir(resultado)
    md = constructor.construir_markdown(resultado)
    assert 'sk-test-1234567890' not in txt
    assert 'sk-test-1234567890' not in md
    assert 'NOTA DE SEGURIDAD' in txt
    assert 'NOTA DE SEGURIDAD' in md


def test_los_dos_formatos_dan_el_mismo_conteo_de_redacciones(constructor, resultado):
    constructor.construir(resultado)
    md = constructor.construir_markdown(resultado)
    assert md.count('[AVISO:') == 1  # solo core/config.py tiene un secreto


# --- Caché ------------------------------------------------------------------

def test_segunda_construccion_no_relee_los_archivos(constructor, resultado, monkeypatch):
    lecturas = []
    original = Path.read_text

    def contar(self, *args, **kwargs):
        lecturas.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', contar)

    primero = constructor.construir(resultado)
    tras_primera = len(lecturas)
    segundo = constructor.construir(resultado)

    assert tras_primera == len(resultado.archivos)
    assert len(lecturas) == tras_primera
    assert segundo == primero


def test_markdown_reusa_lo_procesado_por_txt(constructor, resultado, monkeypatch):
    lecturas = []
    original = Path.read_text

    def contar(self, *args, **kwargs):
        lecturas.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', contar)

    constructor.construir(resultado)
    tras_txt = len(lecturas)
    constructor.construir_markdown(resultado)

    assert len(lecturas) == tras_txt


def test_cambiar_un_archivo_invalida_su_entrada(constructor, resultado):
    constructor.construir(resultado)
    info = next(i for i in resultado.archivos if i.ruta_relativa == 'main.py')

    info.ruta.write_text('contenido nuevo\n', encoding='utf-8')
    os.utime(info.ruta, ns=(1, 1))

    texto = constructor.construir(resultado)
    assert 'contenido nuevo' in texto
    assert 'print("hola")' not in texto


def test_cambiar_opciones_reprocesa(constructor, resultado):
    con_vacias = constructor.construir(resultado)
    assert '\n\n\n' in con_vacias or '\n\n' in con_vacias

    constructor.establecer_opciones(OpcionesOptimizacion(quitar_lineas_vacias=True))
    sin_vacias = constructor.construir(resultado)

    assert sin_vacias != con_vacias
    assert '\n\n\n' not in sin_vacias


def test_archivo_borrado_no_rompe_la_construccion(constructor, resultado):
    info = next(i for i in resultado.archivos if i.ruta_relativa == 'main.py')
    info.ruta.unlink()

    texto = constructor.construir(resultado)
    assert '[Error al leer archivo]' in texto


def test_limpiar_cache_fuerza_relectura(constructor, resultado, monkeypatch):
    constructor.construir(resultado)

    lecturas = []
    original = Path.read_text

    def contar(self, *args, **kwargs):
        lecturas.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', contar)
    constructor.limpiar_cache()
    constructor.construir(resultado)

    assert len(lecturas) == len(resultado.archivos)
