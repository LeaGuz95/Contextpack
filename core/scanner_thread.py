"""
Thread de escaneo para no bloquear la interfaz
"""
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import QThread, Signal

from .scanner import EscanerProyecto, OpcionesFiltro
from .tokenizer import obtener_tokenizador
from models.data_models import ResultadoEscaneo


class HiloEscaneo(QThread):
    """
    Corre el escaneo en un thread separado para mantener la UI responsiva.

    Señales:
        progreso(archivo, numero)  — emitida por cada archivo procesado
        completado(resultado)      — emitida al terminar exitosamente
        error(mensaje)             — emitida si ocurre una excepción
    """

    progreso  = Signal(str, int)           # nombre archivo, número
    completado = Signal(object)            # ResultadoEscaneo
    error     = Signal(str)                # mensaje de error

    def __init__(
        self,
        raiz: Path,
        carpetas: Optional[List[str]] = None,
        dep_archivo: Optional[Path] = None,
        opciones_filtro: Optional[OpcionesFiltro] = None,
        parent=None
    ):
        super().__init__(parent)
        self.raiz       = raiz
        self.carpetas   = carpetas
        self.dep_archivo = dep_archivo
        self._escaner   = EscanerProyecto(opciones_filtro)

    def run(self):
        """Ejecuta el escaneo en el thread secundario"""
        try:
            # Carga el tokenizador aquí: la primera vez tiktoken descarga su
            # vocabulario y no conviene hacerlo en el hilo de la interfaz.
            obtener_tokenizador()

            resultado = self._escaner.escanear(
                self.raiz,
                self.carpetas,
                self.dep_archivo,
                callback_progreso=self._on_progreso,
                cancelado=self.isInterruptionRequested
            )

            if not self.isInterruptionRequested():
                self.completado.emit(resultado)

        except Exception as e:
            if not self.isInterruptionRequested():
                self.error.emit(str(e))

    def _on_progreso(self, archivo: str, numero: int):
        """Callback que recibe el scanner y reemite como señal Qt"""
        if not self.isInterruptionRequested():
            self.progreso.emit(archivo, numero)
