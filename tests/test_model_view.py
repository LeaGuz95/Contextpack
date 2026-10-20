"""Tests de ModeloVista: selección, recorte y consistencia del contexto."""
from pathlib import Path


from core import OpcionesOptimizacion
from core.tokenizer import obtener_tokenizador
from models.data_models import EntradaIgnorada


# --- Estado inicial ---------------------------------------------------------

def test_sin_escaneo_esta_vacio(modelo):
    assert modelo.claves() == []
    assert modelo.archivos_seleccionados() == []
    assert modelo.generar_contexto() == ''
    assert modelo.metricas()['tokens'] == 0


def test_establecer_resultado_lista_todos(modelo, resultado):
    modelo.establecer_resultado(resultado)
    assert len(modelo.claves()) == 4
    assert len(modelo.archivos_seleccionados()) == 4
    assert modelo.exclusiones() == []


# --- Excluir / incluir ------------------------------------------------------

def test_excluir_quita_del_contexto(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.excluir(['core/config.py'])

    assert modelo.esta_excluido('core/config.py')
    seleccionados = [i.ruta_relativa.replace('\\', '/')
                     for i in modelo.archivos_seleccionados()]
    assert 'core/config.py' not in seleccionados
    assert len(seleccionados) == 3


def test_incluir_devuelve_al_contexto(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.excluir(['main.py'])
    modelo.incluir(['main.py'])

    assert not modelo.esta_excluido('main.py')
    assert modelo.exclusiones() == []


def test_reemplazar_exclusiones_ignora_rutas_que_ya_no_existen(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.reemplazar_exclusiones([
        'main.py',
        'archivo_borrado.py',
        'core\\utils.py',
    ])

    assert modelo.esta_excluido('main.py')
    assert modelo.esta_excluido('core/utils.py')
    assert len(modelo.exclusiones()) == 2


def test_reemplazar_exclusiones_quita_las_anteriores(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.excluir(['main.py'])
    modelo.reemplazar_exclusiones(['core/config.py'])

    assert not modelo.esta_excluido('main.py')
    assert modelo.esta_excluido('core/config.py')


def test_excluir_acepta_rutas_con_barras_normalizadas(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.excluir(['core\\utils.py'])
    assert modelo.esta_excluido('core/utils.py')


def test_incluir_todo_y_excluir_todo(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.excluir_todo()
    assert modelo.archivos_seleccionados() == []
    assert len(modelo.exclusiones()) == 4

    modelo.incluir_todo()
    assert len(modelo.archivos_seleccionados()) == 4


def test_exclusiones_son_una_copia(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.excluir(['main.py'])
    lista = modelo.exclusiones()
    lista.clear()
    assert modelo.esta_excluido('main.py')


def test_ignorados_expone_el_detalle_del_escaneo(modelo_con_proyecto):
    entrada = EntradaIgnorada('build/x.py', 'carpeta fija de la app', es_carpeta=True)
    modelo_con_proyecto.resultado.ignorados = [entrada]

    assert modelo_con_proyecto.ignorados() == [entrada]


def test_ignorados_es_una_copia(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.resultado.ignorados = [EntradaIgnorada('x.py', 'motivo')]

    lista = modelo.ignorados()
    lista.clear()

    assert len(modelo.ignorados()) == 1


# --- Resultado filtrado y árbol ---------------------------------------------

def test_arbol_podado_quita_excluidos_y_carpetas_vacias(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.excluir(['core/config.py', 'core/utils.py'])

    arbol = modelo.resultado_filtrado().arbol_directorios
    assert 'core' not in arbol['.']
    assert 'main.py' in arbol['.']
    assert 'docs' in arbol['.']


def test_total_lineas_baja_con_la_seleccion(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    antes = modelo.metricas()['total_lineas']
    modelo.excluir(['docs/README.md'])
    assert modelo.metricas()['total_lineas'] < antes


def test_metricas_reflejan_la_seleccion(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.excluir(['main.py', 'core/utils.py'])
    m = modelo.metricas()

    assert m['archivos_totales'] == 4
    assert m['total_archivos'] == 2
    assert m['archivos_excluidos'] == 2
    assert m['archivos_ignorados'] == 0


# --- Contexto generado ------------------------------------------------------

def test_contexto_solo_incluye_seleccionados(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.excluir(['core/config.py'])
    texto = modelo.generar_contexto()

    assert 'main.py' in texto
    assert 'core/config.py' not in texto


def test_contexto_redacta_secretos(modelo_con_proyecto):
    texto = modelo_con_proyecto.generar_contexto()
    assert 'sk-test-1234567890' not in texto
    assert '[REDACTADO' in texto


def test_cambiar_opciones_invalida_el_cache(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    texto_normal = modelo.generar_contexto()
    assert 'print("hola")' in texto_normal

    modelo.establecer_opciones_optimizacion(
        OpcionesOptimizacion(quitar_lineas_vacias=True)
    )
    texto_optimizado = modelo.generar_contexto()
    assert texto_optimizado != texto_normal


def test_cambiar_seleccion_invalida_el_cache(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    con_todo = modelo.generar_contexto()
    modelo.excluir(['main.py'])
    sin_main = modelo.generar_contexto()

    assert sin_main != con_todo
    assert 'main.py' not in sin_main


def test_cambiar_la_seleccion_no_relee_los_archivos(modelo_con_proyecto, monkeypatch):
    modelo = modelo_con_proyecto
    modelo.generar_contexto_markdown()

    lecturas = []
    original = Path.read_text

    def contar(self, *args, **kwargs):
        lecturas.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', contar)

    modelo.excluir(['core/config.py'])
    modelo.generar_contexto_markdown()

    assert lecturas == []


# --- Recorte por objetivo de tokens -----------------------------------------

def test_recortar_con_objetivo_invalido_no_hace_nada(modelo_con_proyecto):
    assert modelo_con_proyecto.recortar_a(0) == (0, 0)
    assert modelo_con_proyecto.recortar_a(-10) == (0, 0)
    assert len(modelo_con_proyecto.archivos_seleccionados()) == 4


def test_recortar_quita_archivos_y_baja_los_tokens(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    tokens_antes = modelo.metricas()['tokens']
    objetivo = int(tokens_antes * 0.6)

    quitados, ahorrados = modelo.recortar_a(objetivo)

    assert quitados > 0
    assert ahorrados > 0
    assert len(modelo.archivos_seleccionados()) == 4 - quitados
    assert modelo.metricas()['tokens'] <= tokens_antes


def test_recortar_empieza_por_el_archivo_mas_pesado(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    mas_pesado = max(
        modelo.archivos_seleccionados(), key=lambda i: i.tamano_bytes
    )
    clave = mas_pesado.ruta_relativa.replace('\\', '/')
    objetivo = int(modelo.metricas()['tokens'] * 0.5)

    modelo.recortar_a(objetivo)

    assert modelo.esta_excluido(clave)


def test_recortar_deja_de_recortar_si_el_objetivo_es_inalcanzable(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    modelo.recortar_a(1)  # el árbol y las cabeceras son costo fijo
    assert modelo.archivos_seleccionados() == []


# --- Conteo de tokens -------------------------------------------------------

def test_tokens_coinciden_con_lo_que_se_copia(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    tok = obtener_tokenizador()

    markdown = modelo.generar_contexto_markdown()
    assert modelo.metricas()['tokens'] == tok.contar(markdown)


def test_tokens_siguen_coincidiendo_despues_de_recortar(modelo_con_proyecto):
    modelo = modelo_con_proyecto
    tok = obtener_tokenizador()
    modelo.recortar_a(int(modelo.metricas()['tokens'] * 0.7))

    markdown = modelo.generar_contexto_markdown()
    assert modelo.metricas()['tokens'] == tok.contar(markdown)
