"""
Optimización del contenido para reducir tokens sin perder información útil.

Los toggles están apagados por defecto: el contexto se envía tal cual salvo que
el usuario pida lo contrario. Nunca se toca un archivo que no se pueda procesar:
ante cualquier duda se devuelve el contenido original.
"""
import io
import logging
import tokenize
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class OpcionesOptimizacion:
    """Toggles de optimización aplicados al armar el contexto"""
    quitar_comentarios: bool = False
    quitar_lineas_vacias: bool = False

    @property
    def activa(self) -> bool:
        """True si hay al menos una optimización encendida"""
        return self.quitar_comentarios or self.quitar_lineas_vacias


# Extensiones por estilo de comentario
_ESTILO_C = {
    '.js', '.jsx', '.ts', '.tsx', '.java', '.cs', '.go', '.php',
    '.c', '.cpp', '.h', '.hpp', '.rs', '.css', '.scss', '.less',
}
_ESTILO_LINEA = {
    '.yaml', '.yml', '.toml', '.env', '.ini', '.cfg', '.ps1',
    '.sh', '.bash', '.rb',
}
_ESTILO_PYTHON = {'.py'}


class Optimizador:
    """Aplica las optimizaciones pedidas al contenido de un archivo"""

    def optimizar(self, ruta: Path, contenido: str, opciones: OpcionesOptimizacion) -> str:
        """Devuelve el contenido optimizado, o el original si no aplica nada"""
        if not contenido or not opciones.activa:
            return contenido

        estilo = _clave_estilo(ruta)
        texto = contenido

        if opciones.quitar_comentarios:
            texto = self._sin_comentarios(estilo, texto)

        if opciones.quitar_lineas_vacias:
            texto = _sin_lineas_vacias(texto)

        return texto

    @staticmethod
    def _sin_comentarios(estilo: str, texto: str) -> str:
        """Quita comentarios según el estilo del lenguaje"""
        if estilo in _ESTILO_PYTHON:
            return _sin_comentarios_python(texto)
        if estilo in _ESTILO_C:
            return _sin_comentarios_c(texto)
        if estilo in _ESTILO_LINEA:
            return _sin_comentarios_linea(texto)
        return texto


def _clave_estilo(ruta: Path) -> str:
    """Clave de estilo del archivo: su extensión, o '.env' para los archivos .env"""
    nombre = ruta.name.lower()
    if nombre.startswith('.env'):
        return '.env'
    return ruta.suffix.lower()


# ── COMENTARIOS ─────────────────────────────────────────────────────────────

def _sin_comentarios_python(codigo: str) -> str:
    """Quita comentarios usando el tokenizador de Python (no toca strings)"""
    try:
        tokens = [
            tok for tok in tokenize.generate_tokens(io.StringIO(codigo).readline)
            if tok.type != tokenize.COMMENT
        ]
        return _limpiar_lineas(tokenize.untokenize(tokens))
    except Exception:
        logger.debug('No se pudieron quitar comentarios del archivo', exc_info=True)
        return codigo


def _sin_comentarios_c(codigo: str) -> str:
    """Quita // y /* */ respetando strings, template literals y escapes"""
    salida = []
    i = 0
    n = len(codigo)
    en_bloque = False
    cadena = None

    while i < n:
        c = codigo[i]

        if en_bloque:
            if codigo.startswith('*/', i):
                en_bloque = False
                i += 2
            else:
                i += 1
            continue

        if cadena:
            salida.append(c)
            if c == '\\' and i + 1 < n:
                salida.append(codigo[i + 1])
                i += 2
                continue
            if c == cadena:
                cadena = None
            i += 1
            continue

        if c in ('"', "'", '`'):
            cadena = c
            salida.append(c)
            i += 1
            continue

        if codigo.startswith('//', i):
            while i < n and codigo[i] != '\n':
                i += 1
            continue

        if codigo.startswith('/*', i):
            en_bloque = True
            i += 2
            continue

        salida.append(c)
        i += 1

    return _limpiar_lineas(''.join(salida))


def _sin_comentarios_linea(codigo: str) -> str:
    """Quita solo las líneas que son comentario entero (seguro para valores)"""
    lineas = []
    for linea in codigo.splitlines():
        if linea.lstrip().startswith('#'):
            continue
        lineas.append(linea)
    return '\n'.join(lineas)


# ── LÍNEAS VACÍAS ───────────────────────────────────────────────────────────

def _sin_lineas_vacias(texto: str) -> str:
    """Elimina las líneas en blanco (y el espacio sobrante al final de cada una)"""
    return '\n'.join(linea.rstrip() for linea in texto.splitlines() if linea.strip())


def _limpiar_lineas(texto: str) -> str:
    """Saca el espacio sobrante al final de cada línea"""
    return '\n'.join(linea.rstrip() for linea in texto.splitlines())

