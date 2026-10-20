"""Tests de caracterización para Optimizador."""
from pathlib import Path

import pytest


from core.optimizer import OpcionesOptimizacion, Optimizador

COMENTARIOS = OpcionesOptimizacion(quitar_comentarios=True)
VACIAS = OpcionesOptimizacion(quitar_lineas_vacias=True)
AMBAS = OpcionesOptimizacion(quitar_comentarios=True, quitar_lineas_vacias=True)


@pytest.fixture
def opt():
    return Optimizador()


def test_sin_opciones_no_cambia_nada(opt):
    texto = '# comentario\n\na = 1\n\n'
    assert opt.optimizar(Path('a.py'), texto, OpcionesOptimizacion()) == texto


def test_contenido_vacio(opt):
    assert opt.optimizar(Path('a.py'), '', COMENTARIOS) == ''


# --- Python -----------------------------------------------------------------

def test_python_quita_comentarios_y_respeta_strings(opt):
    code = (
        'import os  # comentario\n'
        '# linea entera\n'
        'x = "no # borrar"\n'
        'y = "// tampoco"\n'
    )
    res = opt.optimizar(Path('a.py'), code, COMENTARIOS)
    assert 'comentario' not in res
    assert 'linea entera' not in res
    assert '"no # borrar"' in res
    assert '"// tampoco"' in res


def test_python_respeta_docstrings(opt):
    code = 'def f():\n    """Doc con # y // adentro"""\n    return 1\n'
    res = opt.optimizar(Path('a.py'), code, COMENTARIOS)
    assert '"""Doc con # y // adentro"""' in res


def test_python_con_error_de_sintaxis_devuelve_original(opt):
    code = 'def (:\n# comentario\n'
    assert opt.optimizar(Path('a.py'), code, COMENTARIOS) == code


# --- JavaScript / TypeScript ------------------------------------------------

def test_js_quita_comentarios(opt):
    code = (
        'const a = 1; // uno\n'
        '/* bloque\n   multi */\n'
        'const b = 2;\n'
    )
    res = opt.optimizar(Path('a.js'), code, COMENTARIOS)
    assert 'uno' not in res
    assert 'bloque' not in res
    assert 'const a = 1;' in res
    assert 'const b = 2;' in res


def test_js_respeta_urls_y_templates(opt):
    code = (
        'const u = "http://ejemplo.com/x"; // url\n'
        'const t = `template // adentro`;\n'
    )
    res = opt.optimizar(Path('a.js'), code, COMENTARIOS)
    assert '"http://ejemplo.com/x"' in res
    assert '`template // adentro`' in res


# --- CSS / SCSS -------------------------------------------------------------

def test_css_quita_comentarios_de_bloque(opt):
    code = '/* comentario */\n.a { color: red; }\n'
    res = opt.optimizar(Path('a.css'), code, COMENTARIOS)
    assert 'comentario' not in res
    assert '.a { color: red; }' in res


def test_css_conserva_urls_con_http(opt):
    code = '.a { background: url(http://ejemplo.com/x.png); }\n'
    res = opt.optimizar(Path('a.css'), code, COMENTARIOS)
    assert 'url(http://ejemplo.com/x.png)' in res


def test_scss_si_trata_doble_barra_como_comentario(opt):
    code = '// uno\n.a { color: red; }\n'
    res = opt.optimizar(Path('a.scss'), code, COMENTARIOS)
    assert 'uno' not in res
    assert '.a { color: red; }' in res


# --- YAML / TOML / .env -----------------------------------------------------

def test_yaml_quita_lineas_de_comentario(opt):
    code = '# comentario\nclave: valor\n'
    res = opt.optimizar(Path('a.yml'), code, COMENTARIOS)
    assert 'comentario' not in res
    assert 'clave: valor' in res


def test_yaml_conserva_comentario_en_linea(opt):
    """Caracterización: el comentario inline de YAML queda (es lo seguro)."""
    code = 'clave: valor  # inline\n'
    assert '# inline' in opt.optimizar(Path('a.yml'), code, COMENTARIOS)


def test_toml_quita_comentarios(opt):
    code = '# comentario\n[seccion]\nclave = 1\n'
    res = opt.optimizar(Path('a.toml'), code, COMENTARIOS)
    assert 'comentario' not in res
    assert 'clave = 1' in res


def test_env_quita_comentarios(opt):
    code = '# comentario\nKEY=valor\n'
    res = opt.optimizar(Path('.env'), code, COMENTARIOS)
    assert 'comentario' not in res
    assert 'KEY=valor' in res


# --- Líneas vacías ----------------------------------------------------------

def test_quita_lineas_vacias_y_espacios_finales(opt):
    texto = 'a = 1\n\n\nb = 2   \n\n'
    assert opt.optimizar(Path('a.py'), texto, VACIAS) == 'a = 1\nb = 2'


def test_ambas_opciones(opt):
    texto = '# c\na = 1\n\nb = 2\n'
    assert opt.optimizar(Path('a.py'), texto, AMBAS) == 'a = 1\nb = 2'


# --- Formatos sin estilo conocido -------------------------------------------

def test_extension_desconocida_no_se_toca(opt):
    texto = '# no es un comentario\n\n'
    assert opt.optimizar(Path('a.md'), texto, AMBAS) == '# no es un comentario'


def test_css_conserva_varias_urls(opt):
    code = (
        '@import url(http://fuentes.test/x.css);\n'
        '.a { background: url(https://cdn.test/a.png); }\n'
    )
    res = opt.optimizar(Path('a.css'), code, COMENTARIOS)
    assert 'http://fuentes.test/x.css' in res
    assert 'https://cdn.test/a.png' in res


def test_css_sigue_quitando_comentarios_de_bloque_con_urls(opt):
    code = '/* ver http://ejemplo.com */\n.a { color: red; }\n'
    res = opt.optimizar(Path('a.css'), code, COMENTARIOS)
    assert 'ejemplo.com' not in res
    assert '.a { color: red; }' in res
