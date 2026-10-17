"""
Construcción del contexto para IA
"""
import logging
from typing import Dict, Optional
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

    def establecer_opciones(self, opciones: OpcionesOptimizacion):
        """Cambia las optimizaciones aplicadas al leer cada archivo"""
        self.opciones = opciones

    def establecer_plantilla(self, texto: str):
        """Cambia las instrucciones que se anteponen al contexto"""
        self.plantilla = (texto or "").strip()

    def construir(self, resultado: ResultadoEscaneo) -> str:
        """
        Construye el contexto completo del proyecto.

        Args:
            resultado: Resultado del escaneo

        Returns:
            String con el contexto formateado (datos sensibles redactados)
        """
        total_redacciones = 0

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

        # Agregar contenido de archivos
        for info in sorted(resultado.archivos, key=lambda f: f.ruta_relativa):
            lineas.append(self.cabecera_txt(info))

            contenido_final, n = self._contenido_archivo(info)
            total_redacciones += n

            if n > 0:
                lineas.append(f"# [AVISO: {n} valor(es) sensible(s) redactado(s) en este archivo]")

            lineas.append(contenido_final)
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
        total_redacciones = 0

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

        # Agregar contenido de archivos
        for info in sorted(resultado.archivos, key=lambda f: f.ruta_relativa):
            lineas.append(f"## ARCHIVO: {info.ruta_relativa}")
            lineas.append("")

            contenido_final, n = self._contenido_archivo(info)
            total_redacciones += n

            if n > 0:
                lineas.append(
                    f"> [AVISO: {n} valor(es) sensible(s) redactado(s) en este archivo]"
                )
                lineas.append("")

            lineas.append(f"```{self._lenguaje_fence(info.ruta)}")
            lineas.append(contenido_final)
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

    def _contenido_archivo(self, info) -> tuple:
        """Lee, optimiza y redacta el contenido de un archivo"""
        try:
            contenido = info.ruta.read_text(encoding='utf-8', errors='ignore')
            contenido = self.optimizador.optimizar(info.ruta, contenido, self.opciones)
            contenido_final, n = self.redactor.redactar(info.ruta, contenido)
        except Exception:
            logger.debug('No se pudo procesar %s', info.ruta, exc_info=True)
            info.token_count = 0
            return "[Error al leer archivo]", 0

        info.token_count = self.tokenizador.contar(contenido_final)
        return contenido_final, n

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
