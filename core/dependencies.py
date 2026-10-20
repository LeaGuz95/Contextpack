"""
Análisis de dependencias entre archivos
"""
import ast
import re
import logging
from pathlib import Path
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


class AnalizadorDependencias:
    """Analiza dependencias entre archivos de código"""

    PATRONES = {
        'javascript': [
            r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'require\([\'"]([^\'"]+)[\'"]\)'
        ],
        'csharp': [
            r'using\s+([\w.]+)\s*;',
        ],
        'java': [
            r'import\s+([\w.]+)\s*;',
        ],
    }

    STDLIB_PYTHON = {
        'os', 'sys', 're', 'json', 'math', 'time', 'datetime', 'pathlib',
        'typing', 'collections', 'itertools', 'functools', 'io', 'abc',
        'copy', 'enum', 'dataclasses', 'contextlib', 'threading', 'queue',
        'logging', 'unittest', 'subprocess', 'shutil', 'tempfile', 'glob',
        'hashlib', 'base64', 'urllib', 'http', 'email', 'html', 'xml',
        'csv', 'sqlite3', 'pickle', 'struct', 'socket', 'ssl', 'uuid',
        'random', 'string', 'textwrap', 'pprint', 'traceback', 'inspect',
        'ast', 'dis', 'gc', 'weakref', 'signal', 'platform', 'argparse',
        'django', 'flask', 'fastapi', 'sqlalchemy', 'pydantic', 'celery',
        'requests', 'httpx', 'aiohttp', 'numpy', 'pandas', 'pytest',
        'PySide6', 'PyQt6', 'PIL', 'cv2', 'torch', 'tensorflow',
    }

    STDLIB_JS = {
        'react', 'react-dom', 'vue', 'angular', 'next', 'nuxt',
        'express', 'lodash', 'axios', 'moment', 'dayjs', 'uuid',
        'path', 'fs', 'os', 'http', 'https', 'url', 'events',
        'stream', 'crypto', 'buffer', 'util', 'assert', 'child_process',
    }

    STDLIB_CSHARP = {
        'System', 'Microsoft', 'Newtonsoft', 'NUnit', 'Xunit',
        'AutoMapper', 'FluentValidation', 'MediatR', 'Serilog',
    }

    STDLIB_JAVA = {
        'java', 'javax', 'jakarta', 'org.springframework', 'org.junit',
        'com.fasterxml', 'org.apache', 'org.slf4j', 'ch.qos',
        'org.hibernate', 'org.mockito',
    }

    STDLIB_GO = {
        'fmt', 'os', 'io', 'log', 'net', 'http', 'time', 'math',
        'sort', 'sync', 'errors', 'strings', 'strconv', 'bufio',
        'bytes', 'encoding', 'context', 'reflect', 'runtime', 'path',
        'regexp', 'testing', 'flag', 'crypto', 'hash', 'database',
    }

    # ── EXTRACCIÓN ───────────────────────────────────────────────────────────

    @classmethod
    def extraer_dependencias(cls, archivo: Path) -> List[str]:
        """Extrae las dependencias de un archivo"""
        ext = archivo.suffix.lower()

        if ext == '.py':
            return cls._extraer_deps_python(archivo)
        if ext in ['.js', '.jsx', '.ts', '.tsx']:
            lang = 'javascript'
        elif ext == '.cs':
            lang = 'csharp'
        elif ext == '.java':
            lang = 'java'
        elif ext == '.go':
            return cls._extraer_deps_go(archivo)
        else:
            return []

        try:
            contenido = archivo.read_text(encoding='utf-8', errors='ignore')
            deps = []

            for patron in cls.PATRONES[lang]:
                deps.extend([m.group(1) for m in re.finditer(patron, contenido)])

            # Java: detectar clases del mismo package usadas sin import explícito
            if lang == 'java':
                deps.extend(cls._refs_mismo_package_java(contenido, deps))

            return deps
        except Exception:
            logger.debug('Error extrayendo dependencias de %s', archivo, exc_info=True)
            return []

    @classmethod
    def _extraer_deps_python(cls, archivo: Path) -> List[str]:
        """
        Extrae imports de Python con el AST, no con regex.

        De `from X import Y` salen dos dependencias (`X` y `X.Y`): la segunda
        resuelve cuando Y es un módulo y no molesta cuando es una función.
        De `from . import panel` sale `.panel`, que resuelve a panel.py.
        Si el archivo no compila devuelve lista vacía: el escaneo sigue.
        """
        try:
            fuente = archivo.read_text(encoding='utf-8', errors='ignore')
            arbol = ast.parse(fuente)
        except (OSError, SyntaxError, ValueError):
            logger.debug('No se pudo parsear %s', archivo, exc_info=True)
            return []

        deps = []
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                deps.extend(alias.name for alias in nodo.names)
            elif isinstance(nodo, ast.ImportFrom):
                prefijo = '.' * (nodo.level or 0)
                modulo = nodo.module or ''
                if modulo:
                    deps.append(prefijo + modulo)
                    deps.extend(
                        prefijo + modulo + '.' + alias.name
                        for alias in nodo.names if alias.name != '*'
                    )
                else:
                    deps.extend(
                        prefijo + alias.name
                        for alias in nodo.names if alias.name != '*'
                    )
        return deps

    @classmethod
    def _extraer_deps_go(cls, archivo: Path) -> List[str]:
        """Extrae imports de Go desde un archivo"""
        try:
            contenido = archivo.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            logger.debug('No se pudo leer %s', archivo, exc_info=True)
            return []

        deps = []

        # Import simple: import "paquete"
        for m in re.finditer(r'^import\s+"([^"]+)"', contenido, re.MULTILINE):
            deps.append(m.group(1))

        # Import en bloque: import ( "pkg1"\n "pkg2" )
        bloque = re.search(r'import\s*\(([^)]+)\)', contenido, re.DOTALL)
        if bloque:
            for m in re.finditer(r'(?:[\w]+\s+)?"([^"]+)"', bloque.group(1)):
                dep = m.group(1)
                if dep:
                    deps.append(dep)

        return deps

    @classmethod
    def _refs_mismo_package_java(cls, contenido: str, deps_existentes: List[str]) -> List[str]:
        """
        Detecta clases del mismo package usadas con 'new ClaseX()' sin import explícito.
        Solo agrega si la clase NO está ya cubierta por un import.
        """
        pkg_match = re.search(r'^package\s+([\w.]+)\s*;', contenido, re.MULTILINE)
        if not pkg_match:
            return []

        paquete = pkg_match.group(1)
        clases_importadas = {d.split('.')[-1] for d in deps_existentes}

        nuevas = []
        for clase in re.findall(r'\bnew\s+([A-Z][A-Za-z0-9]+)\s*\(', contenido):
            if clase not in clases_importadas:
                nuevas.append(f"{paquete}.{clase}")
                clases_importadas.add(clase)

        return nuevas

    # ── RESOLUCIÓN ───────────────────────────────────────────────────────────

    @classmethod
    def resolver_dependencias(
        cls,
        dep: str,
        origen: Path,
        raiz: Path
    ) -> List[Path]:
        """
        Resuelve una dependencia retornando lista de archivos.
        C# puede retornar múltiples (todos los .cs del namespace).
        El resto retorna 0 o 1 archivo.
        """
        ext = origen.suffix.lower()

        if ext == '.cs':
            return cls._resolver_csharp(dep, raiz, origen)
        if ext == '.go':
            return cls._resolver_go(dep, origen, raiz)

        resultado = cls._resolver_uno(dep, origen, raiz)
        return [resultado] if resultado else []

    @classmethod
    def _resolver_uno(
        cls,
        dep: str,
        origen: Path,
        raiz: Path
    ) -> Optional[Path]:
        """Resuelve una dependencia a un único archivo"""
        ext = origen.suffix.lower()
        es_python = ext == '.py'
        es_js = ext in ['.js', '.jsx', '.ts', '.tsx']
        es_java = ext == '.java'

        # ── Imports relativos ────────────────────────────────────────────
        if dep.startswith('.'):
            if es_python:
                partes = dep.lstrip('.').replace('.', '/')
                niveles = len(dep) - len(dep.lstrip('.'))
                base = origen.parent
                for _ in range(niveles - 1):
                    base = base.parent
                ruta = base / partes if partes else base
            else:
                ruta = origen.parent / dep.lstrip('./')

            for ext_p in ['.py', '.js', '.jsx', '.ts', '.tsx']:
                c = Path(str(ruta)).with_suffix(ext_p)
                if c.exists() and _es_del_proyecto(c, raiz):
                    return c

            if es_python:
                init = Path(str(ruta)) / '__init__.py'
                if init.exists() and _es_del_proyecto(init, raiz):
                    return init
            return None

        # ── Python absoluto ──────────────────────────────────────────────
        # El proyecto tiene prioridad: un módulo local llamado `queue` o
        # `email` gana sobre el de la biblioteca estándar.
        if es_python:
            raiz_dep = dep.split('.')[0]
            for base in (raiz, raiz / 'src'):
                if not ((base / raiz_dep).exists()
                        or (base / f"{raiz_dep}.py").exists()):
                    continue
                ruta_m = base / dep.replace('.', '/')
                c = ruta_m.with_suffix('.py')
                if c.exists() and _es_del_proyecto(c, raiz):
                    return c
                init = ruta_m / '__init__.py'
                if init.exists() and _es_del_proyecto(init, raiz):
                    return init
            return None

        # ── JS/TS absoluto ───────────────────────────────────────────────
        if es_js:
            dep_l = dep.lstrip('@~/')
            for base in [raiz, raiz / 'src']:
                rm = base / dep_l
                for ext_p in ['.js', '.jsx', '.ts', '.tsx']:
                    c = rm.with_suffix(ext_p)
                    if c.exists() and _es_del_proyecto(c, raiz):
                        return c
                for ext_p in ['.js', '.jsx', '.ts', '.tsx']:
                    c = rm / f'index{ext_p}'
                    if c.exists() and _es_del_proyecto(c, raiz):
                        return c

        # ── Filtrar stdlib (solo si el proyecto no lo tenía) ─────────────
        if es_js and dep.split('.')[0] in cls.STDLIB_JS:
            return None
        if es_java:
            for pkg in cls.STDLIB_JAVA:
                if dep.startswith(pkg):
                    return None

        # ── Java absoluto ────────────────────────────────────────────────
        if es_java:
            for base in [raiz,
                         raiz / 'src' / 'main' / 'java',
                         raiz / 'src' / 'test' / 'java',
                         raiz / 'src']:
                c = (base / dep.replace('.', '/')).with_suffix('.java')
                if c.exists() and _es_del_proyecto(c, raiz):
                    return c
            # Fallback por nombre de clase
            nombre = dep.split('.')[-1]
            for c in raiz.rglob(f'{nombre}.java'):
                if _es_del_proyecto(c, raiz):
                    return c

        return None

    @classmethod
    def _resolver_csharp(cls, dep: str, raiz: Path, origen: Optional[Path] = None) -> List[Path]:
        """
        Resuelve un 'using Namespace' de C# retornando los .cs de la carpeta
        del namespace, filtrando solo los referenciados en el archivo origen.
        """
        if dep.split('.')[0] in cls.STDLIB_CSHARP:
            return []

        segmentos = dep.split('.')

        # Encontrar carpeta del namespace por segmento final
        carpeta_encontrada = None
        carpeta_objetivo = raiz / segmentos[-1]
        if carpeta_objetivo.is_dir():
            carpeta_encontrada = carpeta_objetivo
        else:
            for i in range(len(segmentos), 0, -1):
                for j in range(i):
                    try:
                        carpeta = raiz / Path(*segmentos[j:i])
                    except TypeError:
                        logger.debug('Segmentos inválidos para %s', dep, exc_info=True)
                        continue
                    if carpeta.is_dir():
                        carpeta_encontrada = carpeta
                        break
                if carpeta_encontrada:
                    break

        if not carpeta_encontrada:
            nombre = segmentos[-1]
            for c in raiz.rglob(f'{nombre}.cs'):
                if _es_del_proyecto(c, raiz):
                    return [c]
            return []

        todos = [cs for cs in sorted(carpeta_encontrada.glob('*.cs'))
                 if _es_del_proyecto(cs, raiz)]

        # Sin origen: devolver todos
        if not origen or not origen.exists():
            return todos

        # Filtrar: solo incluir archivos cuyo nombre de clase aparece en el origen
        try:
            contenido_origen = origen.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            logger.debug('No se pudo leer %s', origen, exc_info=True)
            return todos

        filtrados = [
            cs for cs in todos
            if re.search(r'\b' + re.escape(cs.stem) + r'\b', contenido_origen)
        ]

        return filtrados if filtrados else todos

    @classmethod
    def _resolver_go(cls, dep: str, origen: Path, raiz: Path) -> List[Path]:
        """
        Resuelve un import de Go retornando todos los .go de la carpeta.
        Descarta stdlib. Para módulos del proyecto recorta el prefijo del módulo.
        """
        primer_segmento = dep.split('/')[0]

        # Descartar stdlib (sin punto en el primer segmento)
        if '.' not in primer_segmento:
            return []

        modulo = _leer_modulo_go(raiz)

        # Caso 1: import empieza con el nombre del módulo del go.mod
        if modulo and dep.startswith(modulo):
            sub_path = dep[len(modulo):].lstrip('/')
            carpeta = raiz / sub_path
            if carpeta.is_dir():
                return [
                    f for f in sorted(carpeta.glob('*.go'))
                    if not f.name.endswith('_test.go') and _es_del_proyecto(f, raiz)
                ]

        # Caso 2: recortar segmentos del path hasta encontrar carpeta existente
        partes = dep.split('/')
        for i in range(len(partes)):
            sub = raiz / '/'.join(partes[i:])
            if sub.is_dir():
                encontrados = [
                    f for f in sorted(sub.glob('*.go'))
                    if not f.name.endswith('_test.go') and _es_del_proyecto(f, raiz)
                ]
                if encontrados:
                    return encontrados

        return []

    # ── BÚSQUEDA RECURSIVA ───────────────────────────────────────────────────

    @classmethod
    def encontrar_relacionados(
        cls,
        inicial: Path,
        raiz: Path,
        max_prof: int = 3
    ) -> List[Path]:
        """
        Encuentra todos los archivos relacionados recursivamente siguiendo imports.

        Args:
            inicial: Archivo inicial
            raiz: Carpeta raíz del proyecto
            max_prof: Profundidad máxima de búsqueda

        Returns:
            Lista de archivos relacionados (el inicial primero)
        """
        relacionados: List[Path] = []
        procesados: Set[Path] = set()
        cola: List[tuple] = [(inicial, 0)]

        while cola:
            arch, prof = cola.pop(0)

            if arch in procesados or prof > max_prof:
                continue

            procesados.add(arch)
            relacionados.append(arch)

            for dep in cls.extraer_dependencias(arch):
                for dep_arch in cls.resolver_dependencias(dep, arch, raiz):
                    if dep_arch not in procesados:
                        cola.append((dep_arch, prof + 1))

        return relacionados


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _es_del_proyecto(ruta: Path, raiz: Path) -> bool:
    """Verifica que un archivo esté dentro de la raíz del proyecto"""
    try:
        ruta.relative_to(raiz)
        return True
    except ValueError:
        return False


def _leer_modulo_go(raiz: Path) -> Optional[str]:
    """Lee el nombre del módulo desde go.mod"""
    gomod = raiz / 'go.mod'
    if not gomod.exists():
        return None
    try:
        for linea in gomod.read_text(encoding='utf-8').splitlines():
            if linea.strip().startswith('module '):
                return linea.strip().split()[1].strip()
    except Exception:
        logger.debug('No se pudo leer go.mod de %s', raiz, exc_info=True)
    return None