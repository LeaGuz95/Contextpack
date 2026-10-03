"""
Modelos de datos para ContextPack
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict


@dataclass
class InfoArchivo:
    """Información de un archivo escaneado"""
    ruta: Path
    ruta_relativa: str
    lineas: int


@dataclass
class ResultadoEscaneo:
    """Resultado del escaneo de un proyecto"""
    ruta_raiz: Path
    archivos: List[InfoArchivo]
    cantidad_ignorados: int
    total_lineas: int
    arbol_directorios: Dict