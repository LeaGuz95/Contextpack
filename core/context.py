"""
Construcción del contexto para IA
"""
import logging
from typing import Dict, List, Optional, Tuple

from models.data_models import ResultadoEscaneo
from .optimizer import OpcionesOptimizacion, Optimizador
from .redactor import RedactorSensible
from .tokenizer import obtener_tokenizador

logger = logging.getLogger(__name__)


class ConstructorContexto:
    """Construye el contexto formateado para IA"""

    _LENGUAJES_FENCE = {
        '.py': 'python', '.js': 'javascript', '.jsx': 'javascript',
        '.ts': 'typescript', '.tsx': 'typescript', '.cs': 'csharp',
        '.java': 'java', '.go': 'go', '.rb': 'ruby', '.php': 'php',
        '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.json': 'json',
        '.yaml': 'yaml', '.yml': 'yaml', '.xml': 'xml', '.toml': 'toml',
        '.html': 'html', '.css': 'css', '.scss': 'scss',
        '.md': 'markdown', '.txt': 'text',
    }

    def __init__(self, opciones: Optional[OpcionesOptimizacion] = None):
        self.redactor = RedactorSensible()
        self.tokenizador = obtener_tokenizador()
        self.optimizador = Optimizador()
        self.opciones = opciones or OpcionesOptimizacion()
        self.plantilla = ""
        # (ruta, toggles) -> (sello, contenido, tokens, redacciones)
        self._cache: Dict[Tuple, Tuple] = {}

    def establecer_opciones(self, opciones: OpcionesOptimizacion):
        """Cambia las optimizaciones aplicadas al leer cada archivo"""
        if opciones != self.opciones:
            self.opciones = opciones
            self._cache.clear()

    def establecer_plantilla(self, texto: str):
        """Cambia las instrucciones que se anteponen al contexto"""
        self.plantilla = (texto or "").strip()

    def limpiar_cache(self):
        """Olvida el contenido procesado de todos los archivos"""
        self._cache.clear()

    def construir(self, resultado: ResultadoEscaneo) -> str:
        """
        Construye el contexto completo del proyecto en texto plano.

        Args:
            resultado: Resultado del escaneo

        Returns:
            String con el contexto formateado (datos sensibles redactados)
        """
        entradas, total_redacciones = self._procesar(resultado)

        lineas = []

        if self.plantilla:
            lineas.extend([
                "===== INSTRUCCIONES =====",
                self.plantilla,
                ""
            ])

        lineas.extend([
            "===== CONTEXTO DEL PROYECTO =====",
            f"RAÍZ: {resultado.ruta_raiz}",
            f"TOTAL_ARCHIVOS: {len(resultado.archivos)}",
            f"TOTAL_LÍNEAS: {resultado.total_lineas}",
            "",
            "===== ÁRBOL DE DIRECTORIOS =====",
            self._formatear_arbol(resultado.arbol_directorios),
            ""
        ])

        for info, contenido, redacciones in entradas:
            lineas.append(self.cabecera_txt(info))

            if redacciones > 0:
                lineas.append(
                    f"# [AVISO: {redacciones} valor(es) sensible(s) redactado(s) en este archivo]"
                )

            lineas.append(contenido)
            lineas.append("")

        # Nota al pie si hubo redacciones
        if total_redacciones > 0:
            lineas.append(
                f"===== NOTA DE SEGURIDAD =====\n"
                f"Se redactaron {total_redacciones} valor(es) sensible(s) "
                f"(API keys, URLs de BD, contraseñas, tokens).\n"
                f"Los valores fueron reemplazados por [REDACTADO] para proteger información confidencial."
            )

        return "\n".join(lineas)

    def construir_markdown(self, resultado: ResultadoEscaneo) -> str:
        """
        Construye el contexto completo en formato Markdown.
        Usa headers, code fences y blockquotes para que la IA
        distinga claramente entre estructura y contenido de archivos.
        """
        entradas, total_redacciones = self._procesar(resultado)

        lineas = []

        if self.plantilla:
            lineas.extend([
                "# INSTRUCCIONES",
                "",
                self.plantilla,
                "",
                "---",
                ""
            ])

        lineas.extend([
            "# CONTEXTO DEL PROYECTO",
            "",
            f"**RAÍZ:** `{resultado.ruta_raiz}`",
            f"**TOTAL_ARCHIVOS:** {len(resultado.archivos)}",
            f"**TOTAL_LÍNEAS:** {resultado.total_lineas}",
            "",
            "## ÁRBOL DE DIRECTORIOS",
            "",
            "```text",
            self._formatear_arbol(resultado.arbol_directorios),
            "```",
            ""
        ])

        for info, contenido, redacciones in entradas:
            lineas.append(self.cabecera_md(info))
            lineas.append("")

            if redacciones > 0:
                lineas.append(
                    f"> [AVISO: {redacciones} valor(es) sensible(s) redactado(s) en este archivo]"
                )
                lineas.append("")

            lineas.append(f"```{self._lenguaje_fence(info.ruta)}")
            lineas.append(contenido)
            lineas.append("```")
            lineas.append("")

        # Nota al pie si hubo redacciones
        if total_redacciones > 0:
            lineas.append("## NOTA DE SEGURIDAD")
            lineas.append("")
            lineas.append(
                f"- Se redactaron **{total_redacciones}** valor(es) sensible(s) "
                f"(API keys, URLs de BD, contraseñas, tokens).\n"
                f"- Los valores fueron reemplazados por `[REDACTADO]` "
                f"para proteger información confidencial."
            )

        return "\n".join(lineas)

    def cabecera_txt(self, info) -> str:
        """Cabecera que precede a un archivo en el contexto de texto plano"""
        return f"===== ARCHIVO: {info.ruta_relativa} ====="

    def cabecera_md(self, info) -> str:
        """Cabecera que precede a un archivo en el contexto Markdown"""
        return f"## ARCHIVO: {info.ruta_relativa}"

    # ── PROCESAMIENTO POR ARCHIVO ──────────────────────────────────────────

    def _procesar(
        self, resultado: ResultadoEscaneo
    ) -> Tuple[List[Tuple], int]:
        """
        Lee, optimiza y redacta cada archivo una sola vez.

        Returns:
            ([(info, contenido, redacciones), ...], total de redacciones)
        """
        entradas = []
        total_redacciones = 0

        for info in sorted(resultado.archivos, key=lambda f: f.ruta_relativa):
            contenido, redacciones = self._contenido_archivo(info)
            total_redacciones += redacciones
            entradas.append((info, contenido, redacciones))

        return entradas, total_redacciones

    def _contenido_archivo(self, info) -> Tuple[str, int]:
        """
        Devuelve el contenido optimizado y redactado de un archivo.

        Cachea por ruta, toggles y fecha de modificación, así volver a armar
        el contexto sobre los mismos archivos no relee ni re-redacta nada.
        """
        clave = (
            str(info.ruta),
            self.opciones.quitar_comentarios,
            self.opciones.quitar_lineas_vacias,
        )
        sello = self._sello(info.ruta)

        guardado = self._cache.get(clave)
        if guardado and sello is not None and guardado[0] == sello:
            info.token_count = guardado[2]
            return guardado[1], guardado[3]

        try:
            contenido = info.ruta.read_text(encoding='utf-8', errors='ignore')
            contenido = self.optimizador.optimizar(info.ruta, contenido, self.opciones)
            contenido_final, redacciones = self.redactor.redactar(info.ruta, contenido)
        except Exception:
            logger.debug('No se pudo procesar %s', info.ruta, exc_info=True)
            info.token_count = 0
            return "[Error al leer archivo]", 0

        tokens = self.tokenizador.contar(contenido_final)
        info.token_count = tokens

        if sello is not None:
            self._cache[clave] = (sello, contenido_final, tokens, redacciones)

        return contenido_final, redacciones

    @staticmethod
    def _sello(ruta) -> Optional[Tuple[int, int]]:
        """Fecha de modificación y tamaño, para invalidar la caché"""
        try:
            estado = ruta.stat()
        except OSError:
            return None
        return (estado.st_mtime_ns, estado.st_size)

    def _lenguaje_fence(self, ruta) -> str:
        """Devuelve el lenguaje para el code fence según la extensión"""
        if self.redactor.es_archivo_env(ruta):
            return 'env'
        return self._LENGUAJES_FENCE.get(ruta.suffix.lower(), '')

    def _formatear_arbol(
        self,
        arbol: Dict,
        prefijo: str = "",
        ultimo: bool = True
    ) -> str:
        """Formatea el árbol de directorios con caracteres Unicode"""
        lineas = []
        items = sorted(arbol.items(), key=lambda x: (x[1] is not None, x[0]))

        for i, (nombre, sub) in enumerate(items):
            es_ultimo = i == len(items) - 1
            conector = "└── " if es_ultimo else "├── "

            if sub is not None:
                lineas.append(f"{prefijo}{conector}📁 {nombre}/")
                ext = "    " if es_ultimo else "│   "
                hijas = self._formatear_arbol(sub, prefijo + ext, es_ultimo)
                if hijas:
                    lineas.append(hijas)
            else:
                lineas.append(f"{prefijo}{conector}{nombre}")

        return "\n".join(lineas)
