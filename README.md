# ContextPack

App de escritorio (PySide6) que recorre un proyecto y arma un archivo de contexto para
pasarle a un modelo de IA: árbol de directorios más el contenido de los archivos, con los
valores sensibles reemplazados por `[REDACTADO]`.

**v1.10.1** | PySide6 | Leandro Guzmán, Pucha Soft

Repositorio: https://github.com/LeaGuz95/Contextpack

---

## Instalar y ejecutar

### Opción 1: el ejecutable

Descargá `ContextPack.exe` desde la página de
[releases](https://github.com/LeaGuz95/Contextpack/releases/latest). No necesita Python
instalado: doble clic y listo.

### Opción 2: desde el código

Necesitás Python 3.9 o superior.

```bash
git clone https://github.com/LeaGuz95/Contextpack.git
cd Contextpack
```

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

```bash
pip install -r requirements.txt
python main.py
```

Para correr los tests hacen falta las dependencias de desarrollo aparte:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

---

## Cómo se usa

### Flujo normal

1. **Seleccionar**: elegís la carpeta del proyecto.
2. **Escanear**: recorre los archivos y arma el contexto. La barra de progreso muestra
   cuántos archivos lleva y cuál está procesando.
3. Revisás el resultado: árbol a la izquierda, métricas a la derecha, vista previa abajo.
   Con los checkboxes del árbol ajustás qué archivos entran.
4. **Copiar** o **Exportar**.

Los botones se activan solos a medida que corresponde: al arrancar solo funciona
`Seleccionar`; después de elegir carpeta se habilitan `Opciones`, `Analizar`, `Escanear`,
`Nuevo` y `Cargar perfil`; recién cuando termina un escaneo se habilitan `Copiar`,
`Exportar` y las acciones sobre la selección.

### Los botones

| Botón | Qué hace |
|---|---|
| `Seleccionar` | Abre el selector de carpeta. Recuerda la última usada. |
| `⚙️ Opciones` | Lista las carpetas de primer nivel del proyecto y los filtros de escaneo. Al confirmar, escanea directo. |
| `🔍 Analizar` | Abre el árbol de archivos y escanea solo los relacionados con el que elijas, siguiendo imports. |
| `Escanear` | Escaneo completo. Mientras corre se convierte en `⏹ Cancelar`. |
| `🔄 Nuevo` | Limpia todo para empezar con otro proyecto (pide confirmación). |
| `📋 Copiar` | Pega el contexto en Markdown al portapapeles. |
| `💾 Exportar` | Guarda el contexto como `.md` (Markdown) o `.txt` (texto plano). |

**Cancelar**: el botón `Escanear` pasa a `⏹ Cancelar` mientras hay trabajo en curso. Al
cancelar queda un mensaje de "Escaneo cancelado" por 2 segundos y la interfaz se libera.

El escaneo corre en un hilo aparte (`core/scanner_thread.py`), así que la ventana no se
congela aunque el proyecto sea grande.

### Editar la selección

Después de un escaneo, cada archivo y carpeta del árbol tiene un checkbox. Desmarcar un
archivo lo saca del contexto (queda tachado) y los totales de tokens se actualizan al
instante; desmarcar una carpeta saca todo su contenido. Las carpetas muestran un estado
parcial cuando solo una parte de su contenido está seleccionada.

| Botón | Qué hace |
|---|---|
| `☑ Todos` | Vuelve a incluir todo lo escaneado. |
| `⬜ Ninguno` | Excluye todo (útil para elegir a mano unos pocos archivos). |
| `✂️ Recortar…` | Pide un objetivo de tokens y quita los archivos más pesados hasta entrar en ese límite. |
| `📌 Guardar perfil` | Guarda cómo está configurado el proyecto (ver abajo). |
| `↺ Cargar perfil` | Vuelve a dejar todo como estaba al guardar. |

El recorte arranca proponiendo el límite del modelo objetivo elegido (o el 90% del total si
el modelo es `Personalizado`). Al terminar avisa cuántos archivos quitó, cuántos tokens
ahorró y cuántos quedan.

La selección vive en la sesión: al volver a escanear se restablece. Para conservarla entre
sesiones está el perfil.

### Perfiles por proyecto

`📌 Guardar perfil` recuerda **todo** lo que configura al proyecto de una sola vez: las
carpetas elegidas en `⚙️ Opciones`, los filtros de escaneo, los dos toggles de optimización,
el modelo objetivo, la plantilla y la selección de archivos. Se guardan hasta 20 proyectos.

`↺ Cargar perfil` los aplica de vuelta. Si el perfil pide otro escaneo del que tenés en
pantalla —otras carpetas u otros filtros— escanea de nuevo y aplica la selección al terminar;
si coincide con el escaneo actual, cambia la selección al instante.

El botón `↺ Cargar perfil` se habilita apenas elegís la carpeta, antes de escanear: es
justamente para abrir un proyecto y dejarlo como lo tenías sin tener que acordarte de nada.

### Plantillas de contexto

Debajo del modelo objetivo hay un selector de plantilla: el texto que se manda **antes** del
contexto, con lo que le pedís a la IA que haga. Arranca en `Sin plantilla` y trae cinco:

| Plantilla | Pide |
|---|---|
| `Explicar el proyecto` | Arquitectura, módulos, flujo principal y decisiones de diseño. |
| `Refactor y mejoras` | Duplicación, funciones largas, acoplamiento y deuda técnica. |
| `Buscar bugs` | Bugs reales, con archivo, causa y arreglo. |
| `Escribir tests` | Tests con casos borde y el framework asumido. |
| `Documentar` | README, módulos y ejemplos de uso. |

`✏️` abre el editor de la plantilla `Personalizada`; al guardar, el selector queda en
`Personalizada`. La plantilla cuenta en los tokens —se ve en la vista previa y en el total— y
viaja dentro del perfil del proyecto.

En texto plano va como bloque `===== INSTRUCCIONES =====`; en Markdown, como `# INSTRUCCIONES`
antes de `# CONTEXTO DEL PROYECTO`.

### Optimizar el contenido

Arriba del panel de métricas hay dos toggles que se aplican al vuelo —no hace falta volver a
escanear— y quedan guardados en `config.json`:

| Toggle | Qué hace |
|---|---|
| `Sin comentarios` | Quita los comentarios en los lenguajes conocidos. En `.py` usa el tokenizador de Python; en los de estilo C (`.js`, `.jsx`, `.ts`, `.tsx`, `.java`, `.cs`, `.go`, `.php`, `.c`, `.cpp`, `.h`, `.rs`, `.css`, `.scss`) respeta strings y template literals; en los de comentario de línea (`.yaml`, `.yml`, `.toml`, `.ini`, `.cfg`, `.env`, `.sh`, `.bash`, `.ps1`, `.rb`) borra solo las líneas que son comentario entero, para no romper valores que contengan `#`. |
| `Sin líneas vacías` | Saca las líneas en blanco. Se aplica a todos los archivos. |

`Sin comentarios` no toca `.md`, `.txt`, `.json` ni `.html`: no tiene un estilo de comentario
para ellos, así que los deja tal cual.

Medido sobre 8 proyectos reales, quitar comentarios y líneas vacías bajó los tokens entre 2% y
17% según cuánto esté comentado el código. El contenido nunca se recorta a medias: si un
archivo no se puede procesar (por ejemplo, un `.py` que no parsea), se deja tal cual.

### Filtros de escaneo

`⚙️ Opciones` trae, además de las carpetas, los filtros que se aplican durante el escaneo:

| Filtro | Por defecto | Qué hace |
|---|---|---|
| Excluir minificados | Sí | Descarta `*.min.js`, `*.min.css` y similares. |
| Omitir archivos mayores a | 1 MB | Descarta archivos gigantes (bundles, volcados, reportes). |
| Excluir tests y specs | No | Descarta `test_*`, `*_test.py`, `*.spec.ts`, `*.test.js` y las carpetas `test/`, `tests/`, `__tests__/`, `__test__/`, `spec/`, `specs/`. |

El límite de tamaño existe por un caso concreto: en un proyecto real, un único
`release/win-unpacked/LICENSES.chromium.html` de 19,5 MB aportaba 4,13 millones de tokens, el
99% del contexto. Con los valores por defecto ese proyecto pasó de 4.182.452 a 43.149 tokens.

Aparte de estos filtros, el escaneo nunca entra en las carpetas fijas de la app (`.git`,
`node_modules`, `__pycache__`, `venv`, `build`, `dist`, `bin`, `obj`, `out`, `target`,
`release`, `coverage`), en ninguna carpeta que empiece con punto, ni en lo que excluya el
`.gitignore` del proyecto. Por eso un `.py` puede no aparecer aunque exista: si vive dentro de
`build/`, en una carpeta oculta o lo ignora el `.gitignore`, queda fuera.

Para saber qué pasó con cada archivo, hacé clic en **Ignorados** en el panel derecho: abre el
detalle agrupado por motivo —regla del `.gitignore`, tests, tamaño, extensión, carpeta fija…—
con la ruta de cada archivo y un botón para copiar la lista.

### Arrastrar una carpeta

Podés soltar una carpeta del explorador de Windows directamente sobre la ventana: queda como
proyecto activo, igual que con `Seleccionar`.

### Buscar en la vista previa

La barra de búsqueda filtra dentro del texto generado. `Enter` o `▼` va al siguiente
resultado, `▲` al anterior. Cuando no hay más coincidencias vuelve al principio o al final
del documento, según el sentido.

### Menús

- **Archivo → Recientes**: los últimos 10 proyectos escaneados. Al elegir uno solo se
  completa la ruta, hay que volver a pulsar `Escanear`. Las entradas que apuntan a carpetas
  que ya no existen se ocultan solas.
- **Archivo → Limpiar Historial**: vacía la lista de recientes.
- **Archivo → Salir**: cierra la app (guarda tamaño de ventana).
- **Ayuda → Acerca de**: versión y autoría.

---

## Qué entra y qué no

### Extensiones que se incluyen

```
.c  .cpp  .cs  .css  .env  .go  .h  .html  .java  .js  .json
.jsx .md  .php  .py  .rb  .rs  .scss  .toml  .ts  .tsx  .txt
.xml  .yaml  .yml
```

Cualquier otra extensión queda afuera. Por eso no aparecen imágenes (`.png`, `.jpg`,
`.gif`, `.bmp`) ni binarios (`.exe`, `.dll`, `.so`, `.zip`, `.pdf`): no es una regla
aparte, sencillamente no están en la lista.

### Carpetas que se ignoran siempre

```
.git  .venv  __pycache__  bin  build  coverage  dist  env
node_modules  obj  out  release  target  venv
```

Además **toda carpeta cuyo nombre arranque con punto** queda fuera, así que `.github`,
`.vscode`, `.pytest_cache` y similares nunca se escanean.

### Archivos que nunca se incluyen

Estos están explícitamente bloqueados, aunque su extensión sea válida:

```
Pipfile.lock  composer.lock  credentials.json  package-lock.json
poetry.lock   private.key     secrets.json      yarn.lock
```

Los lockfiles se excluyen a propósito: son largos y no aportan nada al contexto de IA.

### Archivos .env

Se incluyen y se redactan. Se reconocen `.env`, `.env.local`, `.env.production`,
`.env.development`, `.env.staging`, `.env.test` y cualquier archivo con extensión `.env`
(por ejemplo `config.env`).

### .gitignore del proyecto

Si el proyecto tiene un `.gitignore` en la raíz, se aplica. Soporta comodines `*`, negaciones
`!` y el sufijo `/` para carpetas. Las negaciones ganan sobre las reglas de exclusión, así
que `!importante.py` fuerza la inclusión de un archivo que otro patrón dejaría afuera.

Solo se lee el `.gitignore` de la raíz, no los de subcarpetas.

---

## Redacción de secretos

`core/redactor.py` reemplaza los valores sensibles por `[REDACTADO]` antes de armar el
contexto. Cuando redacta algo, lo anota: cada archivo afectado lleva un aviso
`[AVISO: N valor(es) sensible(s) redactado(s)]` y al final del documento aparece una
`NOTA DE SEGURIDAD` con el total.

### Archivos .env

Se procesan línea por línea con formato `CLAVE=VALOR`. Se redacta el valor solo si el
**nombre de la clave** coincide con un patrón sensible. `DATABASE_URL`, `API_KEY` o
`STRIPE_SECRET` se tapan; `PORT=3000` o `DEBUG=true` se dejan tal cual, porque no son
secretos. También cubre variantes como `.env.example` o `.env.sample` si llegan al redactor.

### Archivos YAML, TOML e INI

Se procesan línea por línea con formato `clave: valor` o `clave = valor`. Se conserva el
separador original, las comillas de la clave y los comentarios al final de la línea, así
que el archivo sigue siendo válido:

```yaml
database:
  password: [REDACTADO]
  api_key: "[REDACTADO]"   # rotar en prod
```

### Archivos de código

Cubre `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.cs`, `.java`, `.go`, `.rs`, `.rb`, `.php`,
`.json` y `.xml`. Busca:

- URLs de base de datos (`postgres://`, `mysql://`, `mongodb://`, `redis://`, `sqlite://`,
  `mssql://`, `oracle://`) → `[REDACTADO:URL_BD]`
- Tokens `Bearer <algo>` → `[REDACTADO:TOKEN]`
- Formatos de keys conocidas: `sk-` (OpenAI), `ghp_` (GitHub), `xoxb-`/`xoxp-` (Slack),
  `AKIA` (AWS), `AIza` (Google) → `[REDACTADO:API_KEY]`
- Asignaciones con nombre sensible: `api_key = "valor"` → `api_key = "[REDACTADO]"`.
  El nombre puede venir con prefijo (`STRIPE_API_KEY`, `DB_PASSWORD`) y con un sufijo
  habitual (`API_KEY_PROD`, `SECRET_KEY_BASE`). La clave puede ir entre comillas
  (`"api_key": "..."` en JSON), puede estar dentro de un subíndice
  (`os.environ["API_KEY"] = "..."`, `settings['api_key'] = "..."`), el separador puede ser
  `=`, `:` o el `:=` de Go, y el valor puede estar dentro de una llamada
  (`API_KEY = os.getenv("API_KEY", "...")`). El resto de la línea se conserva igual.

### Lo que NO se redacta

Markdown, texto plano, HTML, CSS, SCSS, C, C++ y headers **no pasan por el redactor**. Si
tenés una key escrita en un `.md` o en un `.h`, va a salir tal cual. Revisá la vista previa
antes de exportar.

Dentro de los formatos que sí se redactan quedan estos huecos conocidos:

- Valores sin comillas en código (`PASSWORD = hunter2`).
- Nombres fuera de la lista blanca: `TOKEN = "..."`, `SECRET = "..."` o `key = "..."` no se
  tapan, porque solo se reconocen los nombres del listado (`API_KEY`, `DB_PASSWORD`,
  `STRIPE_SECRET`, `*_TOKEN` con prefijo…). La lista es a propósito: con un comodín se
  redactarían `token_count` o `password_hint`, que no son secretos.
- Bloques multilínea de YAML (`password: |` seguido del valor en las líneas de abajo).
- Secretos embebidos en SQL (`CREATE USER ... IDENTIFIED BY '...'`).
- Credenciales dentro de una URL cuando la clave no tiene nombre sensible
  (`URL=https://usuario:clave@host/x`). Con `DATABASE_URL` o `MONGO_URI` sí se redacta.

Al revés, leer una clave no se redacta porque no hay ningún valor a la vista:
`password = os.environ["DB_PASSWORD"]` sale tal cual.

Por eso Exportar pide marcar "He verificado" antes de escribir el archivo. Para que la
advertencia deje de aparecer, poné `mostrar_advertencia_seguridad` en `false` dentro de
`~/.contextpack/config.json`.

---

## Métricas y ventana de contexto

El panel derecho muestra archivos incluidos, archivos ignorados (con las carpetas que no se
recorrieron aparte, y clic para ver el motivo de cada exclusión), líneas totales y el
**total de tokens** del contexto generado. El conteo lo hace `tiktoken` (encoding
`o200k_base`, con respaldo a `cl100k_base`); si `tiktoken` no está instalado o todavía no
bajó su vocabulario, cae a una estimación offline. El tooltip del número indica cuál se está
usando.

El número corresponde al **Markdown**, que es lo que se copia al portapapeles, se previsualiza
y se usa para la recomendación de recorte. El export `.txt` tiene el mismo contenido con otro
formato, así que su conteo puede diferir en unas pocas centenas de tokens.

También hay un selector **Modelo objetivo** con el límite de cada chat:

| Modelo objetivo | Límite |
|---|---|
| ChatGPT / GPT-4o | 128.000 |
| Claude Sonnet / Opus | 200.000 |
| DeepSeek | 64.000 |
| Grok | 128.000 |
| Gemini 1.5 Pro | 1.000.000 |
| Personalizado | sin límite |

Con un modelo elegido, el aviso dice cuánto del límite estás usando (`Uso: 43%`) o cuántos
tokens sobran. Con `Personalizado` se muestra una guía general por tamaño. La elección queda
guardada en `config.json`.

El árbol de archivos tiene tres columnas — **Archivos**, **Tamaño** y **Tokens** — y las
carpetas muestran el total acumulado de su rama, así se ve de un vistazo qué pesa más.
Cuando hay archivos excluidos, `Archivos` muestra `seleccionados / totales`, y las carpetas
solo suman lo que está seleccionado.

Los toggles de optimización mueven el total de tokens al instante: el conteo siempre refleja lo
que se va a copiar o exportar. `Líneas`, en cambio, es lo que se escaneó, sin descontar la
optimización.

---

## Exportar

`Exportar` propone el nombre `contexto_<nombre_de_la_carpeta>.md` en tu carpeta home, y el
diálogo te deja cambiar la extensión:

- `.md` → formato Markdown, con headers y code fences por archivo. La IA distingue el
  código de la estructura.
- `.txt` → texto plano.

`Copiar` siempre usa Markdown.

---

## Formato de salida

Si elegiste una plantilla, arriba de todo va su bloque de instrucciones:

````markdown
# INSTRUCCIONES

Actuá como desarrollador senior y explicame este proyecto.
...

---

# CONTEXTO DEL PROYECTO
...
````

Salida real de la app sobre un proyecto con `README.md`, `main.py` y `src/utils.py`, donde
`main.py` tenía una API key:

````markdown
# CONTEXTO DEL PROYECTO

**RAÍZ:** `C:\ruta\al\proyecto`
**TOTAL_ARCHIVOS:** 3
**TOTAL_LÍNEAS:** 10

## ÁRBOL DE DIRECTORIOS

```text
├── 📁 ./
│   ├── README.md
│   └── main.py
└── 📁 src/
    └── utils.py
```

## ARCHIVO: README.md

```markdown
# Mi proyecto

Un proyecto de ejemplo.
```

## ARCHIVO: main.py

> [AVISO: 1 valor(es) sensible(s) redactado(s) en este archivo]

```python
import os

API_KEY = '[REDACTADO:API_KEY]'

print(os.getcwd())
```

## ARCHIVO: src\utils.py

```python
def help():
    return 1
```

## NOTA DE SEGURIDAD

- Se redactaron **1** valor(es) sensible(s) (API keys, URLs de BD, contraseñas, tokens).
- Los valores fueron reemplazados por `[REDACTADO]` para proteger información confidencial.
````

Cuando el redactor reconoce el tipo de secreto, el marcador lo dice: `[REDACTADO:API_KEY]`,
`[REDACTADO:URL_BD]` o `[REDACTADO:TOKEN]`. Si solo detectó una asignación con nombre
sensible, deja el `[REDACTADO]` genérico.

Dos detalles que sorprenden al primer uso:

- **La raíz siempre es un nodo `📁 ./`.** Los archivos que están en el primer nivel del
  proyecto quedan adentro de ese nodo, no sueltos al principio del árbol.
- **Las rutas de los archivos usan el separador del sistema**, `src\utils.py` en Windows,
  aunque el árbol de directorios use `/`. Es cosmético, pero desorienta si buscás un archivo
  con Ctrl+F.

El formato `.txt` tiene la misma información en plano, con separadores `=====` en lugar de
headers y sin code fences:

```
===== CONTEXTO DEL PROYECTO =====
RAÍZ: C:\ruta\al\proyecto
TOTAL_ARCHIVOS: 3
TOTAL_LÍNEAS: 10

===== ÁRBOL DE DIRECTORIOS =====
├── 📁 ./
│   ├── README.md
│   └── main.py
└── 📁 src/
    └── utils.py

===== ARCHIVO: README.md =====
# Mi proyecto

Un proyecto de ejemplo.

===== ARCHIVO: main.py =====
# [AVISO: 1 valor(es) sensible(s) redactado(s) en este archivo]
import os

API_KEY = '[REDACTADO:API_KEY]'

print(os.getcwd())

===== ARCHIVO: src\utils.py =====
def help():
    return 1

===== NOTA DE SEGURIDAD =====
Se redactaron 1 valor(es) sensible(s) (API keys, URLs de BD, contraseñas, tokens).
Los valores fueron reemplazados por [REDACTADO] para proteger información confidencial.
```

El `NOTA DE SEGURIDAD` del final solo se agrega cuando hubo redacciones.

---

## Analizar dependencias

`🔍 Analizar` es la vía para meter un proyecto grande en el contexto: en vez de escanearlo
todo, elegís un archivo y se incluye solo lo que ese archivo toca, siguiendo imports de forma
recursiva hasta 3 niveles de profundidad.

Lenguajes con análisis de imports: **Python**, **JavaScript/TypeScript** (`.js`, `.jsx`,
`.ts`, `.tsx`), **C#**, **Java** y **Go**.

Detalles del comportamiento:

- Solo se incluyen archivos que están dentro de la carpeta raíz del proyecto. Las librerías
  externas y la biblioteca estándar se descartan.
- **Java**: además de los `import`, detecta clases del mismo package usadas con `new Clase()`
  sin import explícito.
- **C#**: un `using MiNamespace` trae todos los `.cs` de esa carpeta, filtrados por los
  nombres de clase que aparecen en el archivo original.
- **Go**: lee el nombre del módulo del `go.mod` para resolver imports internos, y excluye los
  archivos `_test.go`.

**Cómo usarlo**: elegís el archivo con un clic y presioná `Analizar`, o hacés doble clic
sobre él y el escaneo arranca directo.

---

## Archivos de configuración y log

Todo va a `~/.contextpack/`:

| Archivo | Contenido |
|---|---|
| `config.json` | Preferencias y proyectos recientes |
| `contextpack.log` | Log de la app, nivel DEBUG |

Claves de `config.json`:

| Clave | Qué es |
|---|---|
| `ultima_carpeta` | Carpeta desde la que abre el selector |
| `proyectos_recientes` | Últimos 10 proyectos, del más reciente al más viejo |
| `mostrar_advertencia_seguridad` | Si Exportar pide marcar "He verificado" |
| `modelo_objetivo` | Modelo elegido en el selector de ventana de contexto |
| `perfiles` | Perfiles guardados con `📌 Guardar perfil`, por proyecto (máx. 20) |
| `plantilla_nombre` | Plantilla elegida en el selector |
| `plantilla_personalizada` | Texto de la plantilla `Personalizada` |
| `quitar_comentarios` | Toggle `Sin comentarios` |
| `quitar_lineas_vacias` | Toggle `Sin líneas vacías` |
| `excluir_tests` | Filtro `Excluir tests y specs` |
| `excluir_minificados` | Filtro `Excluir minificados` (por defecto `true`) |
| `tamano_max_kb` | Tamaño máximo por archivo en KB (por defecto `1024`, `0` = sin límite) |
| `ventana_ancho` / `ventana_alto` | Tamaño de la ventana, guardado al cerrar |

Un `config.json` viejo puede traer claves que ya no se usan (`carpetas_ignoradas_custom`,
`selecciones`): no se borran nunca, y si no hay perfil la `selecciones` de la v1.6.0 se usa
como respaldo de la selección de archivos.

---

## Estructura del proyecto

```
ContextPack/
├── main.py                       # Punto de entrada
├── contextpack.spec              # Configuración de PyInstaller
├── requirements.txt
├── requirements-dev.txt          # pytest, solo para desarrollo
├── pytest.ini
├── logo.ico
├── README.md
├── .gitattributes                # Normalización de finales de línea
├── .gitignore
├── core/
│   ├── __init__.py               # API pública del paquete
│   ├── config.py                 # ConfigManager: preferencias y recientes
│   ├── scanner.py                # EscanerProyecto, FiltroArchivos, OpcionesFiltro
│   ├── scanner_thread.py         # Hilo de escaneo no bloqueante
│   ├── dependencies.py           # AnalizadorDependencias: imports y resolución
│   ├── optimizer.py              # Optimizador: comentarios y líneas vacías
│   ├── redactor.py               # RedactorSensible: API keys, contraseñas, URLs de BD
│   ├── context.py                # ConstructorContexto: salida TXT y Markdown
│   └── tokenizer.py              # Tokenizador: conteo real (tiktoken) o estimado
├── models/
│   ├── __init__.py
│   └── data_models.py            # InfoArchivo, ResultadoEscaneo
├── tests/                        # Suite de pytest (sin Qt salvo los diálogos)
└── ui/
    ├── __init__.py               # API pública del paquete
    ├── main_window.py            # VentanaPrincipal, menú, footer, drag & drop
    ├── main_panel.py             # VistaPanel: controles, árbol, métricas, búsqueda
    ├── dialogs.py                # Carpetas y filtros, archivo a analizar, plantilla
    ├── plantillas.py             # Plantillas de instrucciones para la IA
    ├── model_view.py             # ModeloVista: selección, recorte y caché del contexto
    └── theme.py                  # Hoja de estilos
```

El flujo va `VistaPanel` → `ModeloVista` → `EscanerProyecto` / `AnalizadorDependencias` →
`ConstructorContexto` (que usa `RedactorSensible` y `Tokenizador`). La UI nunca habla directo
con el escáner, y el contexto generado se cachea para no releer y re-redactar todos los
archivos en cada actualización de la vista.

---

## Compilar el ejecutable

PyInstaller no está en `requirements.txt` porque solo hace falta para compilar:

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm contextpack.spec
```

Queda en `dist/ContextPack.exe`. El spec genera un archivo único y sin ventana de consola,
con `logo.ico` embebido. Pesa unos 44 MB (medido sobre el build de v1.4.2), casi todo
PySide6.

Dos detalles del spec:

- `upx=True` está activado. Si no tenés UPX instalado, PyInstaller avisa y sigue sin
  comprimir.
- El `build/` que deja PyInstaller es cache de compilación. `build/` y `dist/` están en
  `.gitignore`.
