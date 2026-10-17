"""
Conteo de tokens para estimar el tamaño del contexto.

Usa tiktoken si está disponible (conteo exacto) y cae a una heurística
offline si no lo está o si no se puede cargar el encoding (por ejemplo,
la primera vez sin conexión para descargar el vocabulario).
"""
import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Encodings preferidos, del más moderno al más antiguo
_ENCODINGS = ('o200k_base', 'cl100k_base', 'p50k_base')

# Heurística offline: las palabras rinden ~4 caracteres por token y cada
# signo de puntuación cuenta como un token. Medido contra tiktoken, acierta
# mejor que len(texto)/4 en código y nunca subestima tanto como este último.
_PATRON_ESPACIOS = re.compile(r'\s')
_PATRON_SIMBOLOS = re.compile(r'[^\sA-Za-z0-9_]')


class Tokenizador:
    """Cuenta tokens con tiktoken si se puede; si no, estima."""

    def __init__(self):
        self._encoder = None
        self._nombre = 'aprox.'
        self._cargar()

    def _cargar(self):
        """Intenta inicializar tiktoken con una caché local del proyecto."""
        cache = Path.home() / '.contextpack' / 'tiktoken'
        try:
            cache.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault('TIKTOKEN_CACHE_DIR', str(cache))
        except OSError:
            logger.debug('No se pudo preparar la caché de tiktoken', exc_info=True)

        try:
            import tiktoken
        except ImportError:
            logger.info('tiktoken no instalado; se usa estimación aproximada')
            return

        for nombre in _ENCODINGS:
            try:
                self._encoder = tiktoken.get_encoding(nombre)
            except Exception:
                logger.debug('Encoding %s no disponible', nombre, exc_info=True)
                continue
            self._nombre = nombre
            logger.info('Tokenizador tiktoken listo (%s)', nombre)
            return

        logger.info('tiktoken sin encoding cargable; se usa estimación aproximada')

    @property
    def nombre(self) -> str:
        """Nombre del encoding en uso, o 'aprox.' si se estima."""
        return self._nombre

    @property
    def exacto(self) -> bool:
        """True si el conteo es exacto (tiktoken disponible)."""
        return self._encoder is not None

    def contar(self, texto: str) -> int:
        """Devuelve la cantidad de tokens de un texto."""
        if not texto:
            return 0

        if self._encoder is not None:
            try:
                return len(self._encoder.encode(texto, disallowed_special=()))
            except Exception:
                logger.debug('Falló el conteo exacto; se estima', exc_info=True)

        return self._estimar(texto)

    @staticmethod
    def _estimar(texto: str) -> int:
        """Heurística offline: ~4 caracteres por token + un token por signo."""
        espacios = len(_PATRON_ESPACIOS.findall(texto))
        simbolos = len(_PATRON_SIMBOLOS.findall(texto))
        caracteres_palabra = len(texto) - espacios - simbolos
        return round(caracteres_palabra / 4 + simbolos)


_tokenizador: Optional[Tokenizador] = None


def obtener_tokenizador() -> Tokenizador:
    """Devuelve la instancia compartida (el encoder se carga una sola vez)."""
    global _tokenizador
    if _tokenizador is None:
        _tokenizador = Tokenizador()
    return _tokenizador
