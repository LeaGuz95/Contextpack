"""
Redacción de datos sensibles en el contexto generado
"""
import re
from pathlib import Path
from typing import Tuple


class RedactorSensible:
    """
    Detecta y redacta datos sensibles antes de exportar el contexto.
    Los valores son reemplazados por [REDACTADO] para que la IA
    entienda la estructura sin ver el valor real.
    """

    ARCHIVOS_ENV = {
        '.env', '.env.local', '.env.production', '.env.development',
        '.env.staging', '.env.test'
    }

    # Nombres sensibles. Acepta prefijo (DB_PASSWORD, STRIPE_API_KEY) y un
    # sufijo acotado (_PROD, _TOKEN, _BASE), que es el que aparece en la
    # práctica. El sufijo es una lista blanca a propósito: con un comodín
    # se redactarían password_hint o token_count, que no son secretos.
    _NOMBRES_BASE = (
        r'api[_-]?key|api[_-]?secret|api[_-]?token|access[_-]?token|'
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
        r'jwt[_-]?secret|jwt[_-]?key|encryption[_-]?key'
    )

    _SUFIJOS = (
        r'(?:[_-](?:key|keys|token|secret|secrets|pass|password|pwd|value|'
        r'base|raw|prod|production|dev|development|staging|stage|'
        r'test|tests|local|old|new|v\d+|\d+))?'
    )

    _NOMBRES = r'(?:' + _NOMBRES_BASE + r')' + _SUFIJOS

    NOMBRES_SENSIBLES = re.compile(r'(?i)(' + _NOMBRES + r')\b')

    PATRONES_VALORES = [
        (re.compile(
            r'((?:postgresql|mysql|mongodb|redis|sqlite|mssql|oracle)'
            r'(?:\+\w+)?://[^\s\'",;)]+)',
            re.IGNORECASE), 'URL_BD'),
        (re.compile(r'(Bearer\s+[A-Za-z0-9\-_\.]+)', re.IGNORECASE), 'TOKEN'),
        (re.compile(
            r'(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|'
            r'xoxb-[A-Za-z0-9\-]{50,}|xoxp-[A-Za-z0-9\-]{50,}|'
            r'AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9\-_]{35})'), 'API_KEY'),
    ]

    # Asignación con el valor pegado al separador, que es el caso normal:
    #   API_KEY = "..."          -> API_KEY = "[REDACTADO]"
    #   os.environ["API_KEY"] = "..."   (clave de subíndice)
    #   apiKey := "..."          (Go)
    # El valor puede ir con comillas dobles, simples o backticks (JS). La
    # comilla de cierre no se consume: queda en el texto.
    _PATRON_ASIG = re.compile(
        r'(?i)(["\']?)(' + _NOMBRES + r')\b(["\']?\s*\]?\s*)(:=|=|:)(\s*)'
        r'(["\'`])(?!\[REDACTADO)(?:(?!\6)[^\n])+?(?=\6)'
    )

    # Valor dentro de una llamada, que no está pegado al separador:
    #   TOKEN = os.getenv("TOKEN", "sk-...")   -> TOKEN = os.getenv("TOKEN", "[REDACTADO]")
    # Entre el separador y el valor se admiten corchetes enteros (`config["x"]`)
    # pero no un `[` suelto, para no redactar la clave de `os.environ["API_KEY"]`.
    _PATRON_ASIG_LLAMADA = re.compile(
        r'(?i)(' + _NOMBRES + r')(\b\s*(?::=|=)\s*(?:[^\[\n]|\[[^"\n]*\])*?,\s*)'
        r'(["\'`])(?!\[REDACTADO)(?:(?!\3)[^\n])+?(?=\3)'
    )

    # Clave de YAML/TOML/INI: indentación, viñeta opcional, clave con
    # comillas opcionales, separador y valor.
    _PATRON_CLAVE_LINEA = re.compile(
        r'^(\s*(?:[-*]\s+)?)("?)([A-Za-z0-9_.\-]+)("?)(\s*[:=]\s*)(.*)$'
    )

    # Marcadores de bloque de YAML (`clave: |`). El valor real está en las
    # líneas siguientes, así que no se toca el marcador.
    _MARCADORES_BLOQUE = {'|', '>', '|-', '>-', '|+', '>+'}

    # Prefiltro barato: todo nombre sensible contiene alguna de estas
    # palabras, así que si no aparece ninguna no vale la pena correr el
    # patrón completo. Sobre un proyecto grande esto ahorra ~90 % del tiempo.
    _CLAVES = (
        'key', 'secret', 'token', 'pass', 'pwd', 'bearer',
        'url', 'uri', 'sid', 'bot', 'string', 'webhook',
    )

    def es_archivo_env(self, ruta: Path) -> bool:
        """Determina si un archivo es de tipo .env"""
        nombre = ruta.name.lower()
        return (nombre in self.ARCHIVOS_ENV
                or nombre.startswith('.env')
                or nombre.endswith('.env'))

    @staticmethod
    def _separar_comentario(valor: str) -> Tuple[str, str]:
        """
        Separa un comentario final (`valor  # nota`) del valor, sin cortar
        dentro de comillas. Devuelve (valor, comentario) y el comentario
        incluye el `#`.
        """
        comilla = None
        for i, caracter in enumerate(valor):
            if comilla:
                if caracter == comilla:
                    comilla = None
            elif caracter in '"\'':
                comilla = caracter
            elif caracter == '#' and i > 0 and valor[i - 1].isspace():
                return valor[:i].rstrip(), valor[i:]
        return valor, ''

    def redactar_env(self, contenido: str) -> Tuple[str, int]:
        """
        Redacta un archivo .env línea a línea.
        Formato: KEY=VALUE -> KEY=[REDACTADO]
        Conserva la indentación, el prefijo `export` y el comentario final.
        """
        lineas = []
        conteo = 0

        for linea in contenido.splitlines():
            linea_strip = linea.strip()

            if not linea_strip or linea_strip.startswith('#') or '=' not in linea:
                lineas.append(linea)
                continue

            cabeza, _, cola = linea.partition('=')
            nombre = cabeza.strip()
            if nombre.lower().startswith('export '):
                nombre = nombre[7:].strip()

            valor, comentario = self._separar_comentario(cola)

            if self.NOMBRES_SENSIBLES.search(nombre) and valor.strip():
                espacios = valor[:len(valor) - len(valor.lstrip())]
                nueva = cabeza + '=' + espacios + '[REDACTADO]'
                if comentario:
                    nueva += ' ' + comentario
                lineas.append(nueva)
                conteo += 1
            else:
                lineas.append(linea)

        return '\n'.join(lineas), conteo

    def redactar_clave_valor(self, contenido: str) -> Tuple[str, int]:
        """
        Redacción línea a línea para YAML, TOML e INI.
        Formato: clave: valor -> clave: [REDACTADO]
        Conserva el separador original (no cambia `:` por `=`), las comillas
        de la clave y el comentario final.
        """
        conteo = 0
        lineas = []

        for linea in contenido.splitlines():
            m = self._PATRON_CLAVE_LINEA.match(linea)
            if not m:
                lineas.append(linea)
                continue

            prefijo, comilla_ini, clave, comilla_fin, separador, valor = m.groups()

            if comilla_ini != comilla_fin:
                lineas.append(linea)
                continue

            valor_limpio, comentario = self._separar_comentario(valor)
            valor_strip = valor_limpio.strip()

            if (self.NOMBRES_SENSIBLES.search(clave)
                    and valor_strip
                    and valor_strip not in self._MARCADORES_BLOQUE):
                comilla = ''
                if len(valor_strip) >= 2 and valor_strip[0] in '"\'' \
                        and valor_strip[-1] == valor_strip[0]:
                    comilla = valor_strip[0]
                nueva = (prefijo + comilla_ini + clave + comilla_fin
                         + separador + comilla + '[REDACTADO]' + comilla)
                if comentario:
                    nueva += ' ' + comentario
                lineas.append(nueva)
                conteo += 1
                continue

            lineas.append(linea)

        return '\n'.join(lineas), conteo

    def _redactar_valores(self, contenido: str) -> Tuple[str, int]:
        """Aplica los patrones de valores conocidos (URL de BD, tokens, API keys)"""
        conteo = 0
        for patron, tipo in self.PATRONES_VALORES:
            contenido, n = patron.subn(
                lambda m, t=tipo: '[REDACTADO:' + t + ']', contenido
            )
            conteo += n
        return contenido, conteo

    def redactar_codigo(self, contenido: str) -> Tuple[str, int]:
        """
        Redacta datos sensibles dentro de archivos de código fuente.
        Primero las asignaciones por nombre, después los valores sueltos
        (el segundo paso ya no ve los valores que tapó el primero).
        """
        if self._puede_haber_secreto(contenido):
            def reemplazar_asig(m):
                # Todo lo de la izquierda se conserva tal cual; la comilla de
                # cierre queda en el texto porque el patrón no la consume.
                return ''.join(m.group(i) for i in range(1, 7)) + '[REDACTADO]'

            contenido, conteo = self._PATRON_ASIG.subn(reemplazar_asig, contenido)

            def reemplazar_llamada(m):
                return m.group(1) + m.group(2) + m.group(3) + '[REDACTADO]'

            contenido, n_llamada = self._PATRON_ASIG_LLAMADA.subn(
                reemplazar_llamada, contenido
            )
            conteo += n_llamada
        else:
            conteo = 0

        contenido, n = self._redactar_valores(contenido)
        return contenido, conteo + n

    def _puede_haber_secreto(self, contenido: str) -> bool:
        """Prefiltro: descarta archivos donde no puede haber un nombre sensible"""
        bajo = contenido.lower()
        return any(clave in bajo for clave in self._CLAVES)

    def redactar(self, ruta: Path, contenido: str) -> Tuple[str, int]:
        """
        Punto de entrada principal. Elige estrategia según el tipo de archivo.
        Retorna el contenido redactado y la cantidad total de redacciones.
        """
        if self.es_archivo_env(ruta):
            return self.redactar_env(contenido)

        extension = ruta.suffix.lower()

        if extension in ('.yaml', '.yml', '.toml', '.ini'):
            contenido, n1 = self.redactar_clave_valor(contenido)
            contenido, n2 = self._redactar_valores(contenido)
            return contenido, n1 + n2

        extensiones_codigo = {
            '.py', '.js', '.ts', '.tsx', '.jsx',
            '.cs', '.java', '.go', '.rs', '.rb', '.php',
            '.json', '.xml'
        }

        if extension in extensiones_codigo:
            return self.redactar_codigo(contenido)

        return contenido, 0
