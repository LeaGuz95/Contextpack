"""
Capa de presentación - Lógica de vista
"""
from typing import Dict, Optional

from core import ConfigManager, ConstructorContexto
from models.data_models import ResultadoEscaneo


class ModeloVista:
    """
    Maneja la lógica de presentación entre Core y UI.
    Cachea el contexto generado para no relevar ni re-redactar
    todos los archivos en cada actualización de la vista.
    """

    def __init__(self, config: ConfigManager):
        self.config = config
        self.constructor = ConstructorContexto()
        self.resultado: Optional[ResultadoEscaneo] = None
        self._contexto = ""
        self._contexto_markdown = ""

    def establecer_resultado(self, resultado: Optional[ResultadoEscaneo]):
        """Fija el resultado del escaneo e invalida la caché de contexto"""
        self.resultado = resultado
        self._contexto = ""
        self._contexto_markdown = ""

    def generar_contexto(self) -> str:
        """Genera (o devuelve cacheado) el contexto formateado"""
        if not self.resultado:
            return ""
        if not self._contexto:
            self._contexto = self.constructor.construir(self.resultado)
        return self._contexto

    def generar_contexto_markdown(self) -> str:
        """Genera (o devuelve cacheado) el contexto en formato Markdown"""
        if not self.resultado:
            return ""
        if not self._contexto_markdown:
            self._contexto_markdown = self.constructor.construir_markdown(self.resultado)
        return self._contexto_markdown

    def metricas(self) -> Dict:
        """Obtiene métricas del escaneo actual"""
        if not self.resultado:
            return {
                'total_archivos': 0,
                'archivos_ignorados': 0,
                'total_lineas': 0,
                'tokens': 0
            }

        ctx = self.generar_contexto()

        return {
            'total_archivos': len(self.resultado.archivos),
            'archivos_ignorados': self.resultado.cantidad_ignorados,
            'total_lineas': self.resultado.total_lineas,
            'tokens': len(ctx) // 4  # Estimación aproximada
        }