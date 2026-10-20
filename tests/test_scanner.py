"""Tests del escáner: qué entra, qué queda fuera y por qué motivo."""
from pathlib import Path

from core import EscanerProyecto, FiltroArchivos, LectorGitignore, OpcionesFiltro
from core.scanner import (
    MOTIVO_CARPETA_OCULTA, MOTIVO_CARPETA_RESERVADA, MOTIVO_CARPETA_TESTS,
    MOTIVO_EXTENSION, MOTIVO_GITIGNORE, MOTIVO_LISTA_NEGRA, MOTIVO_MINIFICADO,
    MOTIVO_TAMANO, MOTIVO_TESTS,
)


def _escribir(base: Path, rel: str, contenido: str = 'print(1)\n') -> Path:
    ruta = base / rel
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding='utf-8')
    return ruta


def _escanear(base: Path, **opciones):
    return EscanerProyecto(OpcionesFiltro(**opciones)).escanear(base)


def _motivos(resultado) -> dict:
    return {
        i.ruta_relativa.replace('\\', '/'): i.motivo
        for i in resultado.ignorados
        if not i.es_carpeta
    }


def _carpetas(resultado) -> dict:
    return {
        i.ruta_relativa.replace('\\', '/'): i.motivo
        for i in resultado.ignorados
        if i.es_carpeta
    }


def test_incluye_los_py_y_no_reporta_nada(tmp_path):
    _escribir(tmp_path, 'main.py')
    _escribir(tmp_path, 'core/utils.py')

    resultado = _escanear(tmp_path)

    assert len(resultado.archivos) == 2
    assert resultado.ignorados == []
    assert resultado.cantidad_ignorados == 0


def test_los_dotfiles_no_ensucian_el_detalle(tmp_path):
    _escribir(tmp_path, '.gitignore', 'otro.py\n')
    _escribir(tmp_path, '.editorconfig', 'root = true\n')
    _escribir(tmp_path, 'main.py')

    resultado = _escanear(tmp_path)

    assert resultado.ignorados == []


def test_motivo_cuando_lo_filtra_el_gitignore(tmp_path):
    _escribir(tmp_path, '.gitignore', 'generado.py\n')
    _escribir(tmp_path, 'generado.py')
    _escribir(tmp_path, 'main.py')

    resultado = _escanear(tmp_path)

    assert [a.ruta_relativa for a in resultado.archivos] == ['main.py']
    assert _motivos(resultado) == {'generado.py': MOTIVO_GITIGNORE}


def test_motivo_cuando_el_gitignore_ignora_la_carpeta(tmp_path):
    _escribir(tmp_path, '.gitignore', 'legacy/\n')
    _escribir(tmp_path, 'legacy/viejo.py')
    _escribir(tmp_path, 'main.py')

    resultado = _escanear(tmp_path)

    assert [a.ruta_relativa for a in resultado.archivos] == ['main.py']
    assert _carpetas(resultado) == {'legacy': MOTIVO_GITIGNORE}


def test_motivo_de_una_carpeta_oculta(tmp_path):
    _escribir(tmp_path, '.nube/script.py')
    _escribir(tmp_path, 'main.py')

    resultado = _escanear(tmp_path)

    assert _carpetas(resultado) == {'.nube': MOTIVO_CARPETA_OCULTA}
    assert resultado.cantidad_ignorados == 0


def test_motivo_de_una_carpeta_reservada(tmp_path):
    _escribir(tmp_path, 'build/generado.py')
    _escribir(tmp_path, 'main.py')

    resultado = _escanear(tmp_path)

    assert _carpetas(resultado) == {'build': MOTIVO_CARPETA_RESERVADA}


def test_excluir_tests_marca_archivo_y_carpeta(tmp_path):
    _escribir(tmp_path, 'test_modelo.py')
    _escribir(tmp_path, 'modelo.py')
    _escribir(tmp_path, 'tests/caso.py')

    resultado = _escanear(tmp_path, excluir_tests=True)

    assert [a.ruta_relativa for a in resultado.archivos] == ['modelo.py']
    assert _motivos(resultado) == {'test_modelo.py': MOTIVO_TESTS}
    assert _carpetas(resultado) == {'tests': MOTIVO_CARPETA_TESTS}


def test_excluir_tests_no_confunde_nombres_parecidos(tmp_path):
    _escribir(tmp_path, 'contest.py')
    _escribir(tmp_path, 'latest.py')

    resultado = _escanear(tmp_path, excluir_tests=True)

    assert len(resultado.archivos) == 2
    assert resultado.ignorados == []


def test_motivo_por_tamano(tmp_path):
    _escribir(tmp_path, 'grande.py', 'x = 1\n' * 400)
    _escribir(tmp_path, 'chico.py')

    resultado = _escanear(tmp_path, tamano_max_kb=1)

    assert [a.ruta_relativa for a in resultado.archivos] == ['chico.py']
    assert _motivos(resultado) == {'grande.py': MOTIVO_TAMANO}


def test_motivo_por_extension_no_soportada(tmp_path):
    _escribir(tmp_path, 'script.pyw')
    _escribir(tmp_path, 'main.py')

    resultado = _escanear(tmp_path)

    assert _motivos(resultado) == {'script.pyw': MOTIVO_EXTENSION}


def test_motivo_por_minificado(tmp_path):
    _escribir(tmp_path, 'app.min.js')
    _escribir(tmp_path, 'app.js')

    resultado = _escanear(tmp_path)

    assert _motivos(resultado) == {'app.min.js': MOTIVO_MINIFICADO}


def test_motivo_por_lista_negra(tmp_path):
    _escribir(tmp_path, 'package-lock.json', '{}\n')
    _escribir(tmp_path, 'package.json', '{}\n')

    resultado = _escanear(tmp_path)

    assert _motivos(resultado) == {'package-lock.json': MOTIVO_LISTA_NEGRA}


def test_los_env_se_incluyen(tmp_path):
    _escribir(tmp_path, '.env', 'API_KEY=secreto\n')

    resultado = _escanear(tmp_path)

    assert [a.ruta_relativa for a in resultado.archivos] == ['.env']


def test_el_conteo_solo_suma_archivos(tmp_path):
    _escribir(tmp_path, 'build/generado.py')
    _escribir(tmp_path, 'notas.rst')
    _escribir(tmp_path, 'main.py')

    resultado = _escanear(tmp_path)

    archivos = [i for i in resultado.ignorados if not i.es_carpeta]
    assert resultado.cantidad_ignorados == len(archivos) == 1


def test_motivo_exclusion_devuelve_none_si_entra(tmp_path):
    ruta = _escribir(tmp_path, 'main.py')
    filtro = FiltroArchivos(
        LectorGitignore(tmp_path), OpcionesFiltro()
    )

    assert filtro.motivo_exclusion(ruta, 'main.py') is None
    assert filtro.debe_incluir_archivo(ruta, 'main.py') is True


def test_motivo_carpeta_devuelve_none_si_entra(tmp_path):
    (tmp_path / 'src').mkdir()
    filtro = FiltroArchivos(
        LectorGitignore(tmp_path), OpcionesFiltro()
    )

    assert filtro.motivo_carpeta('src', 'src') is None
    assert filtro.debe_ignorar_carpeta('src', 'src') is False
