"""
Capa de presentación - Lógica de vista
"""
from typing import Dict, Iterable, List, Optional, Tuple

from core import ConfigManager, ConstructorContexto, OpcionesOptimizacion
from models.data_models import InfoArchivo, ResultadoEscaneo
from .plantillas import SIN_PLANTILLA, texto_plantilla


def clave_ruta(ruta: str) -> str:
    """Normaliza los separadores de una ruta relativa para usarla como clave"""
    return ruta.replace('\\', '/')


class ModeloVista:
    """
    Maneja la lógica de presentación entre Core y UI.

    Guarda el escaneo completo y aparte la selección (los archivos excluidos),
    de modo que el usuario pueda recortar el contexto sin volver a escanear.
    Cachea el contexto generado para no relevar ni re-redactar todos los
    archivos en cada actualización de la vista.
    """

    def __init__(self, config: ConfigManager):
        self.config = config
        self.constructor = ConstructorContexto(self._opciones_config())
        self.constructor.establecer_plantilla(self._plantilla_config())
        self.resultado: Optional[ResultadoEscaneo] = None
        self._excluidos: set = set()
        self._filtrado: Optional[ResultadoEscaneo] = None
        self._contexto = ""
        self._contexto_markdown = ""

    def _opciones_config(self) -> OpcionesOptimizacion:
        """Lee los toggles de optimización guardados en la configuración"""
        cfg = self.config.config
        return OpcionesOptimizacion(
            quitar_comentarios=bool(cfg.get('quitar_comentarios', False)),
            quitar_lineas_vacias=bool(cfg.get('quitar_lineas_vacias', False)),
        )

    def _plantilla_config(self) -> str:
        """Plantilla de instrucciones guardada en la configuración"""
        cfg = self.config.config
        return texto_plantilla(
            cfg.get('plantilla_nombre', SIN_PLANTILLA),
            cfg.get('plantilla_personalizada', ''),
        )

    def establecer_opciones_optimizacion(self, opciones: OpcionesOptimizacion):
        """Cambia las optimizaciones y descarta el contexto cacheado"""
        self.constructor.establecer_opciones(opciones)
        self._invalidar()

    def establecer_plantilla(self, texto: str):
        """Cambia las instrucciones previas al contexto y descarta el cacheado"""
        self.constructor.establecer_plantilla(texto)
        self._invalidar()

    # ── ESCANEO Y SELECCIÓN ────────────────────────────────────────────────

    def establecer_resultado(self, resultado: Optional[ResultadoEscaneo]):
        """Fija el resultado del escaneo y descarta la selección anterior"""
        self.resultado = resultado
        self._excluidos = set()
        self._invalidar()

    def _invalidar(self):
        """Descarta el filtrado y el contexto cacheados"""
        self._filtrado = None
        self._contexto = ""
        self._contexto_markdown = ""

    def claves(self) -> List[str]:
        """Claves normalizadas de todos los archivos del escaneo"""
        if not self.resultado:
            return []
        return [clave_ruta(i.ruta_relativa) for i in self.resultado.archivos]

    def esta_excluido(self, clave: str) -> bool:
        """Indica si un archivo quedó fuera de la selección"""
        return clave in self._excluidos

    def exclusiones(self) -> List[str]:
        """Copia de las claves excluidas"""
        return sorted(self._excluidos)

    def excluir(self, claves: Iterable[str]):
        """Quita archivos de la selección"""
        nuevas = set(claves) - self._excluidos
        if nuevas:
            self._excluidos |= nuevas
            self._invalidar()

    def incluir(self, claves: Iterable[str]):
        """Devuelve archivos a la selección"""
        quitar = set(claves) & self._excluidos
        if quitar:
            self._excluidos -= quitar
            self._invalidar()

    def incluir_todo(self):
        """Selecciona todos los archivos"""
        if self._excluidos:
            self._excluidos = set()
            self._invalidar()

    def excluir_todo(self):
        """Deselecciona todos los archivos"""
        if not self.resultado:
            return
        todas = set(self.claves())
        if todas != self._excluidos:
            self._excluidos = todas
            self._invalidar()

    def archivos_seleccionados(self) -> List[InfoArchivo]:
        """Archivos que hoy forman parte del contexto"""
        if not self.resultado:
            return []
        return [
            info for info in self.resultado.archivos
            if clave_ruta(info.ruta_relativa) not in self._excluidos
        ]

    # ── RECORTE POR OBJETIVO DE TOKENS ─────────────────────────────────────

    def recortar_a(self, objetivo: int) -> Tuple[int, int]:
        """
        Excluye los archivos más pesados hasta bajar del objetivo de tokens.

        Returns:
            (archivos_quitados, tokens_ahorrados)
        """
        if not self.resultado or objetivo <= 0:
            return (0, 0)

        tokens_antes = self.metricas()['tokens']
        quitados = 0
        tok = self.constructor.tokenizador

        for _ in range(200):   # tope de seguridad
            actual = self.metricas()['tokens']
            if actual <= objetivo:
                break

            seleccionados = self.archivos_seleccionados()
            if not seleccionados:
                break

            # Costo estimado de cada archivo dentro del contexto: su contenido
            # más la cabecera que lo precede. El resto del total medido
            # (cabeceras generales y árbol) se trata como costo fijo.
            costos = [
                (info, info.token_count + tok.contar(self.constructor.cabecera_txt(info)))
                for info in seleccionados
            ]
            restante = sum(costo for _, costo in costos)
            overhead = max(actual - restante, 0)

            quitar = []
            for info, costo in sorted(costos, key=lambda par: par[1], reverse=True):
                if overhead + restante <= objetivo:
                    break
                quitar.append(clave_ruta(info.ruta_relativa))
                restante -= costo

            if not quitar:
                break

            self.excluir(quitar)
            quitados += len(quitar)

        return (quitados, tokens_antes - self.metricas()['tokens'])

    # ── CONTEXTO ───────────────────────────────────────────────────────────

    def resultado_filtrado(self) -> Optional[ResultadoEscaneo]:
        """Resultado del escaneo con solo los archivos seleccionados"""
        if self.resultado is None:
            return None
        if not self._excluidos:
            return self.resultado
        if self._filtrado is None:
            self._filtrado = self._construir_filtrado()
        return self._filtrado

    def _construir_filtrado(self) -> ResultadoEscaneo:
        """Arma un ResultadoEscaneo con la selección actual"""
        archivos = self.archivos_seleccionados()
        return ResultadoEscaneo(
            ruta_raiz=self.resultado.ruta_raiz,
            archivos=archivos,
            cantidad_ignorados=self.resultado.cantidad_ignorados,
            total_lineas=sum(info.lineas for info in archivos),
            arbol_directorios=self._podar_arbol(
                self.resultado.arbol_directorios, '', self._excluidos
            ),
        )

    def _podar_arbol(self, arbol: Dict, prefijo: str, excluidos: set) -> Dict:
        """Quita del árbol los archivos excluidos y las carpetas que quedan vacías"""
        podado = {}
        for nombre, sub in arbol.items():
            if nombre == '.':
                # El nodo de la raíz es transparente: sus hijos cuelgan directo
                hijas = self._podar_arbol(sub, '', excluidos)
                if hijas:
                    podado[nombre] = hijas
                continue

            rel = f"{prefijo}/{nombre}" if prefijo else nombre
            if sub is None:
                if rel not in excluidos:
                    podado[nombre] = None
            else:
                hijas = self._podar_arbol(sub, rel, excluidos)
                if hijas:
                    podado[nombre] = hijas
        return podado

    def generar_contexto(self) -> str:
        """Genera (o devuelve cacheado) el contexto en texto plano"""
        if not self.resultado:
            return ""
        if not self._contexto:
            self._contexto = self.constructor.construir(self.resultado_filtrado())
        return self._contexto

    def generar_contexto_markdown(self) -> str:
        """Genera (o devuelve cacheado) el contexto en Markdown"""
        if not self.resultado:
            return ""
        if not self._contexto_markdown:
            self._contexto_markdown = self.constructor.construir_markdown(
                self.resultado_filtrado()
            )
        return self._contexto_markdown

    def metricas(self) -> Dict:
        """Métricas del escaneo actual, ya con la selección aplicada"""
        tok = self.constructor.tokenizador

        if not self.resultado:
            return {
                'total_archivos': 0,
                'archivos_totales': 0,
                'archivos_excluidos': 0,
                'archivos_ignorados': 0,
                'total_lineas': 0,
                'tokens': 0,
                'tokenizador': tok.nombre,
                'tokens_exactos': tok.exacto
            }

        filtrado = self.resultado_filtrado()

        return {
            'total_archivos': len(filtrado.archivos),
            'archivos_totales': len(self.resultado.archivos),
            'archivos_excluidos': len(self._excluidos),
            'archivos_ignorados': self.resultado.cantidad_ignorados,
            'total_lineas': filtrado.total_lineas,
            'tokens': tok.contar(self.generar_contexto()),
            'tokenizador': tok.nombre,
            'tokens_exactos': tok.exacto
        }
