"""
Redacción de datos sensibles en el contexto generado
"""
import re
from pathlib import Path
from typing import List, Tuple


class RedactorSensible:
    """
    Detecta y redacta datos sensibles antes de exportar el contexto.
    Los valores son reemplazados por [REDACTADO] para que la IA
    entienda la estructura sin ver el valor real.
    """

    # Archivos que se procesan línea a línea (formato KEY=VALUE)
    ARCHIVOS_ENV = {
        '.env', '.env.local', '.env.production', '.env.development',
        '.env.staging', '.env.test'
    }

    # Patrones de nombres de variables sensibles (insensible a mayúsculas)
    NOMBRES_SENSIBLES = re.compile(
        r'(?i)(api[_-]?key|api[_-]?secret|api[_-]?token|access[_-]?token|'
        r'auth[_-]?token|bearer|secret[_-]?key|private[_-]?key|'
        r'password|passwd|pwd|database[_-]?url|db[_-]?url|'
        r'connection[_-]?string|mongo[_-]?uri|redis[_-]?url|'
        r'postgres[_-]?url|mysql[_-]?url|smtp[_-]?pass|'
        r'webhook[_-]?secret|signing[_-]?secret|client[_-]?secret|'
        r'github[_-]?token|gitlab[_-]?token|gh[_-]?token|'
        r'aws[_-]?access[_-]?key|aws[_-]?secret|aws[_-]?token|'
        r'stripe[_-]?key|stripe[_-]?secret|stripe[_-]?token|'
        r'twilio[_-]?token|twilio[_-]?sid|twilio[_-]?secret|'
        r'sendgrid[_-]?key|sendgrid[_-]?token|'
        r'firebase[_-]?key|firebase[_-]?secret|'
        r'google[_-]?api[_-]?key|google[_-]?secret|'
        r'slack[_-]?token|slack[_-]?secret|slack[_-]?webhook|'
        r'discord[_-]?token|discord[_-]?secret|'
        r'telegram[_-]?token|telegram[_-]?bot|'
        r'openai[_-]?key|openai[_-]?token|'
        r'anthropic[_-]?key|anthropic[_-]?token|'
        r'jwt[_-]?secret|jwt[_-]?key|encryption[_-]?key)'
    )

    # Patrones de valores que parecen sensibles (para código fuente)
    PATRONES_VALORES = [
        # URLs de bases de datos
        (re.compile(
            r'((?:postgresql|mysql|mongodb|redis|sqlite|mssql|oracle)'
            r'(?:\+\w+)?://[^\s\'"`,;)]+)',
            re.IGNORECASE
        ), 'URL_BD'),

        # Tokens estilo Bearer / JWT
        (re.compile(
            r'(Bearer\s+[A-Za-z0-9\-_\.]+)',
            re.IGNORECASE
        ), 'TOKEN'),

        # API keys de servicios conocidos
        (re.compile(
            r'(sk-[A-Za-z0-9]{20,}|'           # OpenAI
            r'ghp_[A-Za-z0-9]{36}|'             # GitHub
            r'xoxb-[A-Za-z0-9\-]{50,}|'         # Slack bot
            r'xoxp-[A-Za-z0-9\-]{50,}|'         # Slack user
            r'AKIA[A-Z0-9]{16}|'                 # AWS access key
            r'AIza[A-Za-z0-9\-_]{35})',          # Google API
        ), 'API_KEY'),
    ]

    # Nombres sensibles para asignaciones en código (mismos que NOMBRES_SENSIBLES)
    _NOMBRES = (
        r'api[_-]?key|api[_-]?secret|api[_-]?token|access[_-]?token|'
        r'auth[_-]?token|secret[_-]?key|private[_-]?key|'
        r'password|passwd|pwd|database[_-]?url|db[_-]?url|'
        r'connection[_-]?string|webhook[_-]?secret|client[_-]?secret|'
        r'github[_-]?token|gitlab[_-]?token|gh[_-]?token|'
        r'aws[_-]?access[_-]?key|aws[_-]?secret|aws[_-]?token|'
        r'stripe[_-]?key|stripe[_-]?secret|stripe[_-]?token|'
        r'twilio[_-]?token|twilio[_-]?sid|twilio[_-]?secret|'
        r'sendgrid[_-]?key|sendgrid[_-]?token|'
        r'firebase[_-]?key|firebase[_-]?secret|'
        r'google[_-]?api[_-]?key|google[_-]?secret|'
        r'slack[_-]?token|slack[_-]?secret|slack[_-]?webhook|'
        r'discord[_-]?token|discord[_-]?secret|'
        r'telegram[_-]?token|telegram[_-]?bot|'
        r'openai[_-]?key|openai[_-]?token|'
        r'anthropic[_-]?key|anthropic[_-]?token|'
        r'jwt[_-]?secret|jwt[_-]?key|encryption[_-]?key'
    )

    # Asignaciones con comillas simples: nombre = 'valor'
    PATRON_COMILLA_SIMPLE = re.compile(
        r"(?i)\b(" + _NOMBRES + r")\b\s*(?:=|:)\s*'(?!\[REDACTADO)[^']{4,}'"
    )

    # Asignaciones con comillas dobles: nombre = "valor"
    PATRON_COMILLA_DOBLE = re.compile(
        r'(?i)\b(' + _NOMBRES + r')\b\s*(?:=|:)\s*"(?!\[REDACTADO)[^"]{4,}"'
    )

    def es_archivo_env(self, ruta: Path) -> bool:
        """Determina si un archivo es de tipo .env"""
        return ruta.name.lower() in self.ARCHIVOS_ENV or ruta.suffix.lower() == '.env'

    def redactar_env(self, contenido: str) -> Tuple[str, int]:
        """
        Redacta un archivo .env línea a línea.
        Formato: KEY=VALUE → KEY=[REDACTADO]
        Retorna el contenido redactado y la cantidad de redacciones.
        """
        lineas = []
        conteo = 0

        for linea in contenido.splitlines():
            linea_strip = linea.strip()

            # Ignorar comentarios y líneas vacías
            if not linea_strip or linea_strip.startswith('#'):
                lineas.append(linea)
                continue

            # Buscar patrón KEY=VALUE
            if '=' in linea_strip:
                clave, _, valor = linea_strip.partition('=')
                clave_limpia = clave.strip()

                # Redactar si el nombre de la clave parece sensible
                if self.NOMBRES_SENSIBLES.search(clave_limpia) and valor.strip():
                    lineas.append(f"{clave_limpia}=[REDACTADO]")
                    conteo += 1
                else:
                    lineas.append(linea)
            else:
                lineas.append(linea)

        return '\n'.join(lineas), conteo

    def redactar_codigo(self, contenido: str) -> Tuple[str, int]:
        """
        Redacta datos sensibles dentro de archivos de código fuente.
        Aplica patrones de valores conocidos y asignaciones por nombre.
        Retorna el contenido redactado y la cantidad de redacciones.
        """
        conteo = 0

        # Paso 1: patrones de valores reconocibles (URLs de BD, tokens, API keys)
        for patron, tipo in self.PATRONES_VALORES:
            def reemplazar(m, tipo=tipo):
                return f'[REDACTADO:{tipo}]'

            nuevo, n = patron.subn(reemplazar, contenido)
            if n:
                contenido = nuevo
                conteo += n

        # Paso 2: asignaciones con comillas simples
        def reemplazar_simple(m):
            nombre = m.group(1)
            return f"{nombre} = '[REDACTADO]'"

        nuevo, n = self.PATRON_COMILLA_SIMPLE.subn(reemplazar_simple, contenido)
        if n:
            contenido = nuevo
            conteo += n

        # Paso 3: asignaciones con comillas dobles
        def reemplazar_doble(m):
            nombre = m.group(1)
            return f'{nombre} = "[REDACTADO]"'

        nuevo, n = self.PATRON_COMILLA_DOBLE.subn(reemplazar_doble, contenido)
        if n:
            contenido = nuevo
            conteo += n

        return contenido, conteo

    def redactar(self, ruta: Path, contenido: str) -> Tuple[str, int]:
        """
        Punto de entrada principal. Elige estrategia según el tipo de archivo.
        Retorna el contenido redactado y la cantidad total de redacciones.
        """
        if self.es_archivo_env(ruta):
            return self.redactar_env(contenido)

        extension = ruta.suffix.lower()
        extensiones_codigo = {
            '.py', '.js', '.ts', '.tsx', '.jsx',
            '.cs', '.java', '.go', '.rb', '.php',
            '.yaml', '.yml', '.json', '.xml', '.toml'
        }

        if extension in extensiones_codigo:
            return self.redactar_codigo(contenido)

        return contenido, 0