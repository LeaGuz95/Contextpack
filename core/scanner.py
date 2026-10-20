"""
Escaneo de proyectos y filtrado de archivos
"""
import os
import fnmatch
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Callable, Set

from models.data_models import EntradaIgnorada, InfoArchivo, ResultadoEscaneo
from .dependencies import AnalizadorDependencias

logger = logging.getLogger(__name__)


# Motivos por los que un archivo queda fuera del contexto. El texto se muestra
# tal cual en el detalle de la UI, así que va en castellano y sin jerga.
MOTIVO_GITIGNORE = 'regla del .gitignore'
MOTIVO_TESTS = 'excluir tests'
MOTIVO_CARPETA_TESTS = 'carpeta de tests'
MOTIVO_MINIFICADO = 'minificado'
MOTIVO_TAMANO = 'supera el tamaño máximo'
MOTIVO_EXTENSION = 'extensión no soportada'
MOTIVO_LISTA_NEGRA = 'lista negra'
MOTIVO_LECTURA = 'no se pudo leer'
MOTIVO_CARPETA_RESERVADA = 'carpeta fija de la app'
MOTIVO_CARPETA_OCULTA = 'carpeta oculta'


@dataclass
class OpcionesFiltro:
    """Filtros aplicados durante el escaneo"""
    excluir_tests: bool = False
    excluir_minificados: bool = True
    tamano_max_kb: int = 1024   # 0 = sin límite


# Nombres que delatan un archivo de test (test_foo.py, foo.test.ts, foo-spec.js…)
_TOKENS_TEST = {'test', 'tests', 'spec', 'specs'}


def _es_archivo_test(nombre: str) -> bool:
    """Detecta archivos de test por los tokens del nombre (sin falsos positivos)"""
    partes = nombre.lower().replace('-', '.').replace('_', '.').split('.')
    return any(parte in _TOKENS_TEST for parte in partes)


class LectorGitignore:
    """
    Lee y aplica las reglas de un archivo .gitignore.
    Soporta: carpetas, archivos exactos, wildcards (*), negaciones (!).
    """

    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.patrones_ignorar: List[str] = []
        self.patrones_incluir: List[str] = []   # negaciones con !
        self._cargar(raiz / '.gitignore')

    def _cargar(self, ruta: Path):
        """Parsea el .gitignore si existe"""
        if not ruta.exists():
            return

        try:
            for linea in ruta.read_text(encoding='utf-8', errors='ignore').splitlines():
                linea = linea.strip()

                # Ignorar comentarios y líneas vacías
                if not linea or linea.startswith('#'):
                    continue

                # Negaciones — fuerzan inclusión
                if linea.startswith('!'):
                    self.patrones_incluir.append(linea[1:].lstrip('/'))
                else:
                    self.patrones_ignorar.append(linea.lstrip('/'))
        except Exception:
            logger.warning('Error al parsear .gitignore de %s', self.raiz, exc_info=True)

    def debe_ignorar(self, ruta_relativa: str, es_directorio: bool = False) -> bool:
        """
        Evalúa si una ruta relativa debe ser ignorada según el .gitignore.
        Las negaciones tienen prioridad sobre los patrones de ignorar.
        """
        if not self.patrones_ignorar:
            return False

        nombre = Path(ruta_relativa).name

        # Verificar negaciones primero
        for patron in self.patrones_incluir:
            if self._coincide(nombre, ruta_relativa, patron):
                return False

        # Verificar patrones de ignorar
        for patron in self.patrones_ignorar:
            # Patrón de directorio (termina en /)
            if patron.endswith('/'):
                if es_directorio and self._coincide(nombre, ruta_relativa, patron.rstrip('/')):
                    return True
            else:
                if self._coincide(nombre, ruta_relativa, patron):
                    return True

        return False

    def _coincide(self, nombre: str, ruta_relativa: str, patron: str) -> bool:
        """Verifica si un nombre o ruta coincide con un patrón gitignore"""
        # Coincidencia por nombre exacto o wildcard
        if fnmatch.fnmatch(nombre, patron):
            return True

        # Coincidencia por ruta relativa completa
        if fnmatch.fnmatch(ruta_relativa, patron):
            return True

        # Coincidencia con ruta usando separador de directorios
        if fnmatch.fnmatch(ruta_relativa, f'**/{patron}'):
            return True

        return False

    @property
    def activo(self) -> bool:
        """Retorna True si se encontró y cargó un .gitignore"""
        return bool(self.patrones_ignorar or self.patrones_incluir)


class FiltroArchivos:
    """Filtrado de archivos y carpetas"""

    IGNORADAS = {
        '.git', 'node_modules', '__pycache__', 'bin', 'obj',
        'dist', 'build', 'venv', '.venv', 'env',
        'release', 'out', 'target', 'coverage'
    }

    EXTENSIONES = {
        '.py', '.js', '.ts', '.tsx', '.jsx', '.cs', '.java',
        '.json', '.md', '.txt', '.html', '.css', '.yaml', '.yml',
        '.go', '.rs', '.rb', '.php', '.c', '.cpp', '.h',
        '.xml', '.toml', '.scss', '.env'
    }

    ARCHIVOS_ENV = {
        '.env', '.env.local', '.env.production', '.env.development',
        '.env.staging', '.env.test'
    }

    IGNORAR_COMPLETAMENTE = {
        'secrets.json', 'credentials.json', 'private.key',
        'package-lock.json', 'yarn.lock', 'poetry.lock',
        'Pipfile.lock', 'composer.lock'
    }

    CARPETAS_TEST = {'test', 'tests', 'spec', 'specs', '__tests__', '__test__'}

    def __init__(
        self,
        gitignore: Optional[LectorGitignore] = None,
        opciones: Optional[OpcionesFiltro] = None
    ):
        self.gitignore = gitignore
        self.opciones = opciones or OpcionesFiltro()

    def motivo_carpeta(self, nombre: str, ruta_relativa: str = '') -> Optional[str]:
        """
        Motivo por el que una carpeta se omite, o None si se recorre.

        Las carpetas fijas y las ocultas también se reportan: son las que más
        desconciertan cuando el código fuente vive en `build/` o similar.
        """
        if nombre in self.IGNORADAS:
            return MOTIVO_CARPETA_RESERVADA

        if nombre.startswith('.'):
            return MOTIVO_CARPETA_OCULTA

        if self.opciones.excluir_tests and nombre.lower() in self.CARPETAS_TEST:
            return MOTIVO_CARPETA_TESTS

        # Reglas del .gitignore
        if self.gitignore and self.gitignore.activo:
            rel = ruta_relativa or nombre
            if self.gitignore.debe_ignorar(rel, es_directorio=True):
                return MOTIVO_GITIGNORE

        return None

    def debe_ignorar_carpeta(self, nombre: str, ruta_relativa: str = '') -> bool:
        """Determina si una carpeta debe ser ignorada"""
        return self.motivo_carpeta(nombre, ruta_relativa) is not None

    def motivo_exclusion(self, ruta: Path, ruta_relativa: str = '') -> Optional[str]:
        """
        Motivo por el que un archivo queda fuera, o None si se incluye.

        Los .env se incluyen siempre: el redactor se encarga de su contenido.
        """
        nombre = ruta.name.lower()

        if nombre in self.IGNORAR_COMPLETAMENTE:
            return MOTIVO_LISTA_NEGRA

        # Los minificados no aportan nada al contexto y pueden ser enormes
        if self.opciones.excluir_minificados and '.min.' in nombre:
            return MOTIVO_MINIFICADO

        if self.opciones.excluir_tests and _es_archivo_test(ruta.name):
            return MOTIVO_TESTS

        # Verificar .gitignore antes de incluir
        if self.gitignore and self.gitignore.activo:
            rel = ruta_relativa or ruta.name
            if self.gitignore.debe_ignorar(rel, es_directorio=False):
                return MOTIVO_GITIGNORE

        if nombre in self.ARCHIVOS_ENV:
            return None

        if ruta.suffix.lower() not in self.EXTENSIONES:
            return MOTIVO_EXTENSION

        if self.opciones.tamano_max_kb:
            try:
                if ruta.stat().st_size > self.opciones.tamano_max_kb * 1024:
                    return MOTIVO_TAMANO
            except OSError:
                pass

        return None

    def debe_incluir_archivo(self, ruta: Path, ruta_relativa: str = '') -> bool:
        """
        Determina si un archivo debe ser incluido.
        Los archivos .env se incluyen y serán redactados.
        """
        return self.motivo_exclusion(ruta, ruta_relativa) is None


class EscanerProyecto:
    """Escanea proyectos y genera resultados"""

    def __init__(self, opciones_filtro: Optional[OpcionesFiltro] = None):
        self.opciones_filtro = opciones_filtro or OpcionesFiltro()
        self.filtro = FiltroArchivos(opciones=self.opciones_filtro)
        self.gitignore: Optional[LectorGitignore] = None

    def escanear(
        self,
        raiz: Path,
        carpetas: Optional[List[str]] = None,
        dep_archivo: Optional[Path] = None,
        callback_progreso: Optional[Callable[[str, int], None]] = None,
        cancelado: Optional[Callable[[], bool]] = None
    ) -> ResultadoEscaneo:
        """
        Escanea un proyecto.

        Args:
            raiz: Carpeta raíz del proyecto
            carpetas: Carpetas específicas a escanear (opcional)
            dep_archivo: Archivo inicial para análisis de dependencias (opcional)
            callback_progreso: Llamada por cada archivo (nombre, numero)
            cancelado: Retorna True si se solicitó cancelación

        Returns:
            ResultadoEscaneo con información del escaneo
        """
        # Cargar .gitignore si existe
        self.gitignore = LectorGitignore(raiz)
        self.filtro = FiltroArchivos(self.gitignore, self.opciones_filtro)

        if dep_archivo:
            return self._escanear_dependencias(
                raiz, dep_archivo, callback_progreso, cancelado
            )

        archivos = []
        detalle_ignorados: List[EntradaIgnorada] = []
        lineas = 0
        contador = 0
        arbol: Dict = {}

        # Una sola pasada: cuenta archivos y construye el árbol de directorios
        for ruta_dir, dirs, files in os.walk(raiz):

            if cancelado and cancelado():
                break

            rel_dir = Path(ruta_dir).relative_to(raiz)
            dirs[:] = self._filtrar_dirs(dirs, rel_dir, detalle_ignorados)

            if self._excluida_por_carpetas(rel_dir, carpetas):
                dirs.clear()
                continue

            nivel = self._nodo_arbol(arbol, rel_dir)

            for f in files:

                if cancelado and cancelado():
                    break

                arch = Path(ruta_dir) / f
                rel_arch = str(rel_dir / f) if str(rel_dir) != '.' else f

                motivo = self.filtro.motivo_exclusion(arch, ruta_relativa=rel_arch)
                if motivo is not None:
                    # Los dotfiles sin extensión soportada (.gitignore,
                    # .editorconfig…) nunca interesan y ensucian el detalle.
                    if motivo != MOTIVO_EXTENSION or not f.startswith('.'):
                        detalle_ignorados.append(EntradaIgnorada(rel_arch, motivo))
                    continue

                try:
                    info = self._leer_info(arch, raiz)
                    archivos.append(info)
                    lineas += info.lineas
                    contador += 1
                    self._agregar_archivo_al_arbol(nivel, f)

                    if callback_progreso:
                        callback_progreso(f, contador)

                except Exception:
                    detalle_ignorados.append(EntradaIgnorada(rel_arch, MOTIVO_LECTURA))
                    logger.debug('No se pudo leer %s', arch, exc_info=True)

        return ResultadoEscaneo(
            ruta_raiz=raiz,
            archivos=archivos,
            cantidad_ignorados=sum(
                1 for i in detalle_ignorados if not i.es_carpeta
            ),
            total_lineas=lineas,
            arbol_directorios=arbol,
            ignorados=detalle_ignorados,
        )

    def _escanear_dependencias(
        self,
        raiz: Path,
        inicial: Path,
        callback_progreso: Optional[Callable[[str, int], None]] = None,
        cancelado: Optional[Callable[[], bool]] = None
    ) -> ResultadoEscaneo:
        """Escanea archivos relacionados por dependencias"""
        archivos_rel = AnalizadorDependencias.encontrar_relacionados(inicial, raiz)
        archivos = []
        detalle_ignorados: List[EntradaIgnorada] = []
        lineas = 0
        contador = 0

        for arch in archivos_rel:

            if cancelado and cancelado():
                break

            rel_arch = str(arch.relative_to(raiz))

            motivo = self.filtro.motivo_exclusion(arch, ruta_relativa=rel_arch)
            if motivo is not None:
                if motivo != MOTIVO_EXTENSION or not arch.name.startswith('.'):
                    detalle_ignorados.append(EntradaIgnorada(rel_arch, motivo))
                continue

            try:
                info = self._leer_info(arch, raiz)
                archivos.append(info)
                lineas += info.lineas
                contador += 1

                if callback_progreso:
                    callback_progreso(arch.name, contador)

            except Exception:
                detalle_ignorados.append(EntradaIgnorada(rel_arch, MOTIVO_LECTURA))
                logger.debug('No se pudo leer %s', arch, exc_info=True)

        arbol: Dict = {}
        for info in archivos:
            self._agregar_archivo_al_arbol(arbol, info.ruta_relativa)

        return ResultadoEscaneo(
            ruta_raiz=raiz,
            archivos=archivos,
            cantidad_ignorados=sum(
                1 for i in detalle_ignorados if not i.es_carpeta
            ),
            total_lineas=lineas,
            arbol_directorios={'.': arbol} if arbol else {},
            ignorados=detalle_ignorados,
        )

    # ── HELPERS ─────────────────────────────────────────────────────────────

    def _leer_info(self, arch: Path, raiz: Path) -> InfoArchivo:
        """Arma la InfoArchivo de un archivo incluido, contando sus líneas"""
        lineas = 0
        with arch.open('r', encoding='utf-8', errors='ignore') as f:
            for _ in f:
                lineas += 1

        return InfoArchivo(
            ruta=arch,
            ruta_relativa=str(arch.relative_to(raiz)),
            lineas=lineas,
            tamano_bytes=self._tamano(arch),
        )

    @staticmethod
    def _agregar_archivo_al_arbol(arbol: Dict, rel_arch: str):
        """Insertar un archivo en el árbol de directorios, creando los nodos"""
        partes = Path(rel_arch).parts
        nivel = arbol
        for parte in partes[:-1]:
            nivel = nivel.setdefault(parte, {})
        nivel[partes[-1]] = None

    @staticmethod
    def _tamano(arch: Path) -> int:
        """Tamaño en bytes de un archivo, o 0 si no se puede leer"""
        try:
            return arch.stat().st_size
        except OSError:
            return 0

    def _filtrar_dirs(
        self,
        dirs: List[str],
        rel_dir: Path,
        detalle_ignorados: Optional[List[EntradaIgnorada]] = None,
    ) -> List[str]:
        """Filtra los subdirectorios según las reglas del proyecto y .gitignore"""
        mantener = []
        for d in dirs:
            rel = str(rel_dir / d) if str(rel_dir) != '.' else d
            motivo = self.filtro.motivo_carpeta(d, rel)
            if motivo is None:
                mantener.append(d)
            elif detalle_ignorados is not None:
                detalle_ignorados.append(EntradaIgnorada(rel, motivo, es_carpeta=True))
        return mantener

    def _excluida_por_carpetas(self, rel_dir: Path, carpetas: Optional[List[str]]) -> bool:
        """Determina si un directorio está fuera de las carpetas seleccionadas"""
        return bool(carpetas) and bool(rel_dir.parts) and rel_dir.parts[0] not in carpetas

    def _nodo_arbol(self, arbol: Dict, rel_dir: Path) -> Dict:
        """Navega (o crea) el nodo del árbol correspondiente a un directorio"""
        partes = rel_dir.parts if rel_dir.parts else ('.',)
        nivel = arbol
        for parte in partes:
            if parte not in nivel:
                nivel[parte] = {}
            nivel = nivel[parte]
        return nivel