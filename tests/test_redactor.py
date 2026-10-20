"""Tests de caracterización para RedactorSensible."""
import tempfile
from pathlib import Path

import pytest

from core.redactor import RedactorSensible


@pytest.fixture
def redactor():
    return RedactorSensible()


# --- .env -------------------------------------------------------------------

def test_env_sin_prefijo_ni_comillas(redactor):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / '.env'
        p.write_text('DB_PASSWORD=secreto123\n', encoding='utf-8')
        res, n = redactor.redactar(p, p.read_text(encoding='utf-8'))
    assert n == 1
    assert res == 'DB_PASSWORD=[REDACTADO]'


def test_env_con_prefijo_de_servicio(redactor):
    res, n = redactor.redactar(
        Path('.env'), 'STRIPE_API_KEY=sk_live_123\nSENDGRID_KEY=SG.abc\n'
    )
    assert n == 2
    assert 'sk_live_123' not in res
    assert 'SG.abc' not in res


def test_env_conserva_export_y_comentario(redactor):
    res, n = redactor.redactar(
        Path('.env'), 'export DB_PASSWORD=hunter2 # rotar en prod\n'
    )
    assert n == 1
    assert res == 'export DB_PASSWORD=[REDACTADO] # rotar en prod'


def test_env_no_toca_claves_no_sensibles(redactor):
    entrada = 'PORT=3000\nDEBUG=true\nLOG_LEVEL=info\n'
    res, n = redactor.redactar(Path('.env'), entrada)
    assert n == 0
    assert res.strip() == entrada.strip()


def test_env_variantes_como_example(redactor):
    res, n = redactor.redactar(
        Path('.env.example'), 'API_KEY=placeholder-1234\n'
    )
    assert n == 1
    assert 'placeholder-1234' not in res


def test_env_con_extension_env(redactor):
    res, n = redactor.redactar(
        Path('config.env'), 'DB_PASSWORD=hunter2\nPORT=3000\n'
    )
    assert n == 1
    assert 'PORT=3000' in res


# --- Código fuente ----------------------------------------------------------

def test_python_comillas_simples_y_dobles(redactor):
    code = '''API_KEY = "sk-test-1234567890"
api_key = 'sk-test-0987654321'
DB_PASSWORD = "supersecreto"
'''
    res, n = redactor.redactar(Path('config.py'), code)
    assert n == 3
    assert 'sk-test' not in res
    assert 'supersecreto' not in res


def test_python_nombres_con_prefijo(redactor):
    code = '''STRIPE_API_KEY = "sk_live_123"
GITHUB_TOKEN = "ghp_123456789012345678901234567890123456"
OPENAI_API_KEY = "sk-proj-123"
'''
    res, n = redactor.redactar(Path('keys.py'), code)
    assert n == 3


def test_python_nombres_con_sufijo(redactor):
    code = '''API_KEY_PROD = "sk_live_999"
SECRET_KEY_BASE = "s3cr3t0"
DB_PASSWORD_DEV = "devpass"
'''
    res, n = redactor.redactar(Path('settings.py'), code)
    assert n == 3
    assert 's3cr3t0' not in res
    assert 'devpass' not in res


def test_asignacion_en_kwarg_y_dict(redactor):
    code = 'connect(password="hunter2", timeout=30)\n'
    res, n = redactor.redactar(Path('client.py'), code)
    assert n == 1
    assert 'hunter2' not in res
    assert 'timeout=30' in res


def test_no_redacta_os_getenv(redactor):
    code = 'password = os.environ["DB_PASSWORD"]\n'
    res, n = redactor.redactar(Path('cfg.py'), code)
    assert n == 0
    assert res.strip() == code.strip()


def test_asignacion_a_subindice(redactor):
    """os.environ["API_KEY"] = "..." y settings['api_key'] = "..." también se tapan"""
    code = '''os.environ["API_KEY"] = "sk-test-1234567890"
settings['api_key'] = "otro-secreto-largo"
'''
    res, n = redactor.redactar(Path('setup.py'), code)
    assert n == 2
    assert 'sk-test' not in res
    assert 'otro-secreto-largo' not in res
    assert 'os.environ["API_KEY"] = "[REDACTADO]"' in res


def test_operador_declaracion_de_go(redactor):
    """Go usa `:=`, que no es ni `=` ni `:`"""
    code = 'apiKey := "sk-test-1234567890"\n'
    res, n = redactor.redactar(Path('main.go'), code)
    assert n == 1
    assert res == 'apiKey := "[REDACTADO]"\n'


def test_valor_dentro_de_una_llamada(redactor):
    """El valor por defecto de un getenv no está pegado al `=`"""
    code = 'API_KEY = os.getenv("API_KEY", "sk-test-1234567890")\n'
    res, n = redactor.redactar(Path('cfg.py'), code)
    assert n == 1
    assert res == 'API_KEY = os.getenv("API_KEY", "[REDACTADO]")\n'


def test_rust_se_redacta(redactor):
    """Rust se escanea y se le quitan comentarios, así que también se redacta"""
    code = 'let api_key = "sk-test-1234567890";\n'
    res, n = redactor.redactar(Path('main.rs'), code)
    assert n == 1
    assert 'sk-test' not in res


def test_no_redacta_la_clave_que_se_lee(redactor):
    """Leer una clave del entorno o de un diccionario no es un secreto en el código"""
    code = '''password = os.environ["DB_PASSWORD"]
api_key = config["default_api_key"]
'''
    res, n = redactor.redactar(Path('cfg.py'), code)
    assert n == 0
    assert res == code


def test_json_mantiene_estructura(redactor):
    data = '{"api_key": "abc123def", "timeout": 30}'
    res, n = redactor.redactar(Path('config.json'), data)
    assert n == 1
    assert res == '{"api_key": "[REDACTADO]", "timeout": 30}'


def test_valores_conocidos(redactor):
    code = 'DATABASE_URL = "postgresql://user:pass@host/db"\n'
    res, n = redactor.redactar(Path('db.py'), code)
    assert n >= 1
    assert 'user:pass' not in res


def test_idempotente(redactor):
    code = 'API_KEY = "sk-test-1234567890"\n'
    una, _ = redactor.redactar(Path('a.py'), code)
    dos, n = redactor.redactar(Path('a.py'), una)
    assert dos == una
    assert n == 0


@pytest.mark.parametrize('code', [
    'timeout = "30"\n',
    'password_hint = "abc"\n',
    'token_count = "12"\n',
    'max_tokens = "4096"\n',
    'auth_token_expiry = "3600"\n',
    'PASSWORD_STRENGTH = "high"\n',
])
def test_falsos_positivos(redactor, code):
    res, n = redactor.redactar(Path('config.py'), code)
    assert n == 0
    assert res.strip() == code.strip()


# --- YAML / TOML / INI ------------------------------------------------------

def test_yaml_sin_comillas(redactor):
    texto = '''database:
  password: mi_pass
  api_key: abc123def456
'''
    res, n = redactor.redactar(Path('config.yml'), texto)
    assert n == 2
    assert 'mi_pass' not in res
    assert 'abc123def456' not in res
    assert 'password: [REDACTADO]' in res


def test_yaml_conserva_el_separador(redactor):
    res, n = redactor.redactar(Path('config.yml'), 'password: mi_pass\n')
    assert n == 1
    assert res == 'password: [REDACTADO]'
    assert '=' not in res


def test_yaml_clave_entre_comillas(redactor):
    res, n = redactor.redactar(Path('config.yml'), '"password": hunter2\n')
    assert n == 1
    assert 'hunter2' not in res
    assert res == '"password": [REDACTADO]'


def test_yaml_item_de_lista(redactor):
    texto = 'servers:\n  - password: hunter2\n  - host: db\n'
    res, n = redactor.redactar(Path('config.yml'), texto)
    assert n == 1
    assert 'hunter2' not in res
    assert '- host: db' in res


def test_yaml_valor_entre_comillas_y_comentario(redactor):
    res, n = redactor.redactar(
        Path('config.yml'), 'api_key: "abc123" # temporal\n'
    )
    assert n == 1
    assert res == 'api_key: "[REDACTADO]" # temporal'


def test_yaml_bloque_no_rompe_el_marcador(redactor):
    texto = 'password: |\n  hunter2\n'
    res, n = redactor.redactar(Path('config.yml'), texto)
    assert n == 0
    assert res.strip() == texto.strip()


def test_yaml_claves_no_sensibles(redactor):
    texto = 'timeout: 30\nversion: "1.2.3"\n'
    res, n = redactor.redactar(Path('config.yml'), texto)
    assert n == 0


def test_toml(redactor):
    texto = '[db]\npassword = "hunter2"\nport = 5432\n'
    res, n = redactor.redactar(Path('config.toml'), texto)
    assert n == 1
    assert 'hunter2' not in res
    assert 'port = 5432' in res


def test_ini(redactor):
    res, n = redactor.redactar(
        Path('setup.ini'), '[auth]\napikey=hunter2\n'
    )
    assert n == 1
    res, n = redactor.redactar(Path('setup.ini'), '[auth]\napi_key=hunter2\n')
    assert n == 1
    assert 'hunter2' not in res


# --- Formatos fuera del redactor (decisión documentada) ---------------------

@pytest.mark.parametrize('nombre,texto', [
    ('README.md', '# Notas\nMi API_KEY es sk-fake-pero-quiero-que-quede\n'),
    ('notas.txt', 'DB_PASSWORD=hunter2\n'),
    ('index.html', '<input value="sk-live-1234567890">'),
    ('style.css', '/* password: hunter2 */\n'),
    ('main.c', 'const char *password = "hunter2";\n'),
])
def test_formatos_fuera_del_redactor(redactor, nombre, texto):
    res, n = redactor.redactar(Path(nombre), texto)
    assert n == 0
    assert res.strip() == texto.strip()


def test_todos_los_nombres_pasan_el_prefiltro():
    """El prefiltro solo es seguro si ning?n nombre sensible se le escapa."""
    for alternativa in RedactorSensible._NOMBRES_BASE.split('|'):
        assert any(clave in alternativa for clave in RedactorSensible._CLAVES), alternativa


def test_el_prefiltro_no_tapa_secretos_entre_texto_normal(redactor):
    code = (
        'def suma(a, b):\n'
        '    return a + b\n'
        '\n'
        'API_KEY = "sk-test-1234567890"\n'
    )
    res, n = redactor.redactar(Path('normal.py'), code)
    assert n == 1
    assert 'sk-test-1234567890' not in res
