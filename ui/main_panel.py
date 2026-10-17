"""
Panel principal de la aplicación
"""
from pathlib import Path
from typing import Dict, List
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QLabel, QSplitter, QMessageBox, QLineEdit, QApplication,
    QProgressBar, QComboBox, QHeaderView, QInputDialog, QCheckBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor

from core import ConfigManager, HiloEscaneo, OpcionesFiltro, OpcionesOptimizacion
from .model_view import ModeloVista, clave_ruta
from .dialogs import DialogoSelectorCarpetas, DialogoAnalizarDep, DialogoPlantilla
from .plantillas import PLANTILLAS, PERSONALIZADA, SIN_PLANTILLA, texto_plantilla


# Modelos objetivo: (etiqueta, límite de tokens) — None = sin límite
MODELOS_OBJETIVO = [
    ("Personalizado", None),
    ("ChatGPT / GPT-4o (128k)", 128000),
    ("Claude Sonnet / Opus (200k)", 200000),
    ("DeepSeek (64k)", 64000),
    ("Grok (128k)", 128000),
    ("Gemini 1.5 Pro (1M)", 1000000),
]


class VistaPanel(QWidget):
    """Panel principal con controles y vistas"""

    def __init__(self, modelo: ModeloVista, config: ConfigManager):
        super().__init__()
        self.modelo = modelo
        self.config = config
        self.ruta = None
        self._hilo = None          # referencia al thread activo
        self._carpetas_pendientes = None
        self._dep_pendiente = None
        self._filtro_pendiente = None
        self._carpetas_usadas = None   # lo que realmente cubre el escaneo actual
        self._filtro_usado = None
        self._seleccion_pendiente = None   # exclusión a aplicar al terminar
        self._cargando_perfil = False      # evita refrescos intermedios
        self._tokens_actuales = 0
        self._mapa_archivos = {}
        self._poblando = False     # evita reaccionar a cambios propios del árbol
        self._init_ui()

    def _init_ui(self):
        """Inicializa la interfaz"""
        layout = QVBoxLayout(self)

        self._crear_botones_superiores(layout)
        self._crear_busqueda(layout)
        self._crear_barra_progreso(layout)
        self._crear_area_arbol(layout)

        layout.addWidget(QLabel("Vista Previa:"))
        self.txt_prev = QTextEdit()
        self.txt_prev.setReadOnly(True)
        layout.addWidget(self.txt_prev, 2)

    def _crear_botones_superiores(self, layout):
        """Crea la barra de botones superior"""
        top = QHBoxLayout()

        self.lbl_ruta = QLabel("Sin proyecto")
        top.addWidget(self.lbl_ruta, 1)

        self.btn_sel = QPushButton("Seleccionar")
        self.btn_sel.clicked.connect(self._seleccionar)

        self.btn_opc = QPushButton("⚙️ Opciones")
        self.btn_opc.clicked.connect(self._opciones)
        self.btn_opc.setEnabled(False)

        self.btn_dep = QPushButton("🔍 Analizar")
        self.btn_dep.clicked.connect(self._dependencias)
        self.btn_dep.setEnabled(False)

        self.btn_esc = QPushButton("Escanear")
        # `clicked` emite un bool que si no se descarta cae en `carpetas`
        self.btn_esc.clicked.connect(lambda *_: self._escanear())
        self.btn_esc.setEnabled(False)

        self.btn_nvo = QPushButton("🔄 Nuevo")
        self.btn_nvo.clicked.connect(self._nuevo)
        self.btn_nvo.setEnabled(False)

        self.btn_cop = QPushButton("📋 Copiar")
        self.btn_cop.clicked.connect(self._copiar)
        self.btn_cop.setEnabled(False)

        self.btn_exp = QPushButton("💾 Exportar")
        self.btn_exp.clicked.connect(self._exportar)
        self.btn_exp.setEnabled(False)

        for btn in [self.btn_sel, self.btn_opc, self.btn_dep,
                    self.btn_esc, self.btn_nvo, self.btn_cop, self.btn_exp]:
            top.addWidget(btn)

        layout.addLayout(top)

    def _crear_busqueda(self, layout):
        """Crea la barra de búsqueda"""
        busq = QHBoxLayout()
        busq.addWidget(QLabel("🔍"))

        self.txt_busq = QLineEdit()
        self.txt_busq.setPlaceholderText("Buscar...")
        self.txt_busq.returnPressed.connect(self._buscar)
        busq.addWidget(self.txt_busq)

        btn_ant = QPushButton("▲")
        btn_ant.clicked.connect(lambda: self._buscar(False))
        btn_ant.setMaximumWidth(40)

        btn_sig = QPushButton("▼")
        btn_sig.clicked.connect(lambda: self._buscar(True))
        btn_sig.setMaximumWidth(40)

        busq.addWidget(btn_ant)
        busq.addWidget(btn_sig)

        layout.addLayout(busq)

    def _crear_barra_progreso(self, layout):
        """Crea la barra de progreso (oculta por defecto)"""
        self.barra_progreso = QProgressBar()
        self.barra_progreso.setRange(0, 0)       # modo indeterminado
        self.barra_progreso.setVisible(False)
        self.barra_progreso.setMaximumHeight(6)
        self.barra_progreso.setTextVisible(False)

        self.lbl_progreso = QLabel("")
        self.lbl_progreso.setVisible(False)
        self.lbl_progreso.setStyleSheet("color: gray; font-size: 11px;")

        layout.addWidget(self.barra_progreso)
        layout.addWidget(self.lbl_progreso)

    def _crear_barra_seleccion(self) -> QHBoxLayout:
        """Crea la barra de acciones sobre la selección de archivos"""
        barra = QHBoxLayout()
        barra.addWidget(QLabel("Selección:"))

        self.btn_todos = QPushButton("☑ Todos")
        self.btn_todos.setToolTip("Incluir todos los archivos")
        self.btn_todos.clicked.connect(self._seleccionar_todo)

        self.btn_ninguno = QPushButton("⬜ Ninguno")
        self.btn_ninguno.setToolTip("Excluir todos los archivos")
        self.btn_ninguno.clicked.connect(self._deseleccionar_todo)

        self.btn_recorte = QPushButton("✂️ Recortar…")
        self.btn_recorte.setToolTip(
            "Quitar los archivos más pesados hasta bajar del objetivo de tokens"
        )
        self.btn_recorte.clicked.connect(self._recortar)

        # Los botones de perfil tocan más que la selección, por eso van a la
        # derecha y separados del resto
        self.btn_guardar_perfil = QPushButton("📌 Guardar perfil")
        self.btn_guardar_perfil.setToolTip(
            "Recordar de este proyecto: carpetas, filtros, optimización,\n"
            "plantilla y selección de archivos"
        )
        self.btn_guardar_perfil.clicked.connect(self._guardar_perfil)

        self.btn_cargar_perfil = QPushButton("↺ Cargar perfil")
        self.btn_cargar_perfil.setToolTip(
            "Volver a dejar todo como estaba cuando guardaste el perfil"
        )
        self.btn_cargar_perfil.clicked.connect(self._cargar_perfil)

        # Estas cinco piden un escaneo hecho: sin resultado no hay nada que tocar
        self._botones_seleccion = [
            self.btn_todos, self.btn_ninguno, self.btn_recorte,
            self.btn_guardar_perfil
        ]

        for btn in self._botones_seleccion:
            btn.setEnabled(False)
            barra.addWidget(btn)

        barra.addStretch()

        self.btn_cargar_perfil.setEnabled(False)
        barra.addWidget(self.btn_cargar_perfil)
        return barra

    def _crear_area_arbol(self, layout):
        """Crea el área con el editor de selección y las métricas"""
        split = QSplitter(Qt.Horizontal)

        izquierda = QWidget()
        il = QVBoxLayout(izquierda)
        il.setContentsMargins(0, 0, 0, 0)
        il.addLayout(self._crear_barra_seleccion())

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Archivos", "Tamaño", "Tokens"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.itemChanged.connect(self._on_item_cambiado)
        il.addWidget(self.tree)
        split.addWidget(izquierda)

        # Refresco con retardo: marcar una carpeta emite muchos cambios seguidos
        self._timer_refresco = QTimer(self)
        self._timer_refresco.setSingleShot(True)
        self._timer_refresco.setInterval(150)
        self._timer_refresco.timeout.connect(self._refrescar_metricas)

        metricas = QWidget()
        ml = QVBoxLayout(metricas)

        ml.addWidget(QLabel("Modelo objetivo:"))
        self.cmb_modelo = QComboBox()
        for etiqueta, limite in MODELOS_OBJETIVO:
            self.cmb_modelo.addItem(etiqueta, limite)
        self._restaurar_modelo()
        self.cmb_modelo.currentIndexChanged.connect(self._on_modelo_cambiado)
        ml.addWidget(self.cmb_modelo)

        ml.addSpacing(10)
        ml.addWidget(QLabel("Plantilla:"))
        fila_plantilla = QHBoxLayout()
        fila_plantilla.setContentsMargins(0, 0, 0, 0)

        self.cmb_plantilla = QComboBox()
        self.cmb_plantilla.addItems([SIN_PLANTILLA, *PLANTILLAS.keys(), PERSONALIZADA])
        self.cmb_plantilla.setToolTip(
            "Instrucciones que se anteponen al contexto al copiar o exportar"
        )
        self._restaurar_plantilla()
        self.cmb_plantilla.currentIndexChanged.connect(self._on_plantilla_cambiada)
        fila_plantilla.addWidget(self.cmb_plantilla, 1)

        self.btn_plantilla = QPushButton("✏️")
        self.btn_plantilla.setMaximumWidth(34)
        self.btn_plantilla.setToolTip("Editar la plantilla personalizada")
        self.btn_plantilla.clicked.connect(self._editar_plantilla)
        fila_plantilla.addWidget(self.btn_plantilla)

        ml.addLayout(fila_plantilla)

        ml.addSpacing(10)
        ml.addWidget(QLabel("Optimizar contexto:"))

        self.chk_comentarios = QCheckBox("Sin comentarios")
        self.chk_comentarios.setToolTip(
            "Quita los comentarios en los lenguajes conocidos\n"
            "(Python, JS/TS, C#, Java, Go, PHP, Rust, CSS, YAML…)"
        )
        self.chk_vacias = QCheckBox("Sin líneas vacías")
        self.chk_vacias.setToolTip("Elimina las líneas en blanco del contenido")

        self._restaurar_optimizacion()
        for chk in [self.chk_comentarios, self.chk_vacias]:
            chk.toggled.connect(self._on_optimizacion_cambiada)
            ml.addWidget(chk)

        ml.addSpacing(10)
        self.lbl_files  = QLabel("Archivos: 0")
        self.lbl_ign    = QLabel("Ignorados: 0")
        self.lbl_lines  = QLabel("Líneas: 0")
        self.lbl_tokens = QLabel("Tokens: 0")
        self.lbl_rec    = QLabel("")
        self.lbl_rec.setWordWrap(True)

        for lbl in [self.lbl_files, self.lbl_ign, self.lbl_lines,
                    self.lbl_tokens, self.lbl_rec]:
            ml.addWidget(lbl)
        ml.addStretch()

        split.addWidget(metricas)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)

        layout.addWidget(split, 1)

    def _restaurar_modelo(self):
        """Restaura el modelo objetivo guardado en la configuración"""
        guardado = self.config.config.get('modelo_objetivo', 'Personalizado')
        idx = self.cmb_modelo.findText(guardado)
        if idx >= 0:
            self.cmb_modelo.setCurrentIndex(idx)

    def _on_modelo_cambiado(self):
        """Persiste el modelo objetivo y recalcula la recomendación"""
        self.config.config['modelo_objetivo'] = self.cmb_modelo.currentText()
        self.config.guardar()
        self._actualizar_recomendacion()

    def _restaurar_plantilla(self):
        """Restaura la plantilla elegida la última vez"""
        guardada = self.config.config.get('plantilla_nombre', SIN_PLANTILLA)
        idx = self.cmb_plantilla.findText(guardada)
        self.cmb_plantilla.setCurrentIndex(idx if idx >= 0 else 0)

    def _texto_plantilla(self) -> str:
        """Texto de las instrucciones según la plantilla elegida"""
        return texto_plantilla(
            self.cmb_plantilla.currentText(),
            self.config.config.get('plantilla_personalizada', ''),
        )

    def _on_plantilla_cambiada(self):
        """Aplica la plantilla elegida al constructor de contexto"""
        self.config.config['plantilla_nombre'] = self.cmb_plantilla.currentText()
        self.config.guardar()

        self.modelo.establecer_plantilla(self._texto_plantilla())
        if not self._cargando_perfil and self.modelo.resultado:
            self._refrescar_metricas()

    def _editar_plantilla(self):
        """Edita el texto de la plantilla personalizada"""
        actual = self.config.config.get('plantilla_personalizada') or self._texto_plantilla()
        dlg = DialogoPlantilla(actual, self)
        if not dlg.exec():
            return

        self.config.config['plantilla_personalizada'] = dlg.texto()
        if self.cmb_plantilla.currentText() == PERSONALIZADA:
            self._on_plantilla_cambiada()
        else:
            self.cmb_plantilla.setCurrentText(PERSONALIZADA)

    def _restaurar_optimizacion(self):
        """Restaura los toggles de optimización guardados"""
        cfg = self.config.config
        self.chk_comentarios.setChecked(bool(cfg.get('quitar_comentarios', False)))
        self.chk_vacias.setChecked(bool(cfg.get('quitar_lineas_vacias', False)))

    def _on_optimizacion_cambiada(self):
        """Aplica y persiste los toggles de optimización"""
        opciones = OpcionesOptimizacion(
            quitar_comentarios=self.chk_comentarios.isChecked(),
            quitar_lineas_vacias=self.chk_vacias.isChecked(),
        )
        self.config.config['quitar_comentarios'] = opciones.quitar_comentarios
        self.config.config['quitar_lineas_vacias'] = opciones.quitar_lineas_vacias
        self.config.guardar()

        self.modelo.establecer_opciones_optimizacion(opciones)
        if not self._cargando_perfil and self.modelo.resultado:
            self._refrescar_metricas()

    def _opciones_filtro(self) -> OpcionesFiltro:
        """Filtros de escaneo guardados en la configuración"""
        cfg = self.config.config
        return OpcionesFiltro(
            excluir_tests=bool(cfg.get('excluir_tests', False)),
            excluir_minificados=bool(cfg.get('excluir_minificados', True)),
            tamano_max_kb=int(cfg.get('tamano_max_kb', 1024)),
        )

    # ── ACCIONES ────────────────────────────────────────────────────────────

    def abrir_carpeta(self, ruta: Path):
        """Fija la carpeta del proyecto y habilita las acciones"""
        self.ruta = Path(ruta)
        self.lbl_ruta.setText(str(self.ruta))

        for btn in [self.btn_esc, self.btn_opc, self.btn_dep, self.btn_nvo]:
            btn.setEnabled(True)

        # Se puede restaurar un perfil antes de escanear: para eso sirve
        self.btn_cargar_perfil.setEnabled(True)

        self.config.config['ultima_carpeta'] = str(self.ruta)
        self.config.guardar()

    def _nuevo(self):
        """Reinicia para escanear otro proyecto"""
        if self._hilo and self._hilo.isRunning():
            return

        respuesta = QMessageBox.question(self, "Cambiar", "¿Cambiar a otro proyecto?")
        if respuesta != QMessageBox.Yes:
            return

        self._timer_refresco.stop()
        self.ruta = None
        self._tokens_actuales = 0
        self._mapa_archivos = {}
        self._carpetas_usadas = None
        self._filtro_usado = None
        self._seleccion_pendiente = None
        self.lbl_ruta.setText("Sin proyecto")
        self.tree.clear()
        self.txt_prev.clear()
        self.txt_busq.clear()

        for lbl in [self.lbl_files, self.lbl_ign, self.lbl_lines, self.lbl_tokens]:
            lbl.setText(lbl.text().split(':')[0] + ": 0")
            lbl.setToolTip("")
        self.lbl_rec.setText("")

        for btn in [self.btn_esc, self.btn_opc, self.btn_dep,
                    self.btn_cop, self.btn_exp, self.btn_nvo,
                    self.btn_cargar_perfil] + self._botones_seleccion:
            btn.setEnabled(False)

        self.modelo.establecer_resultado(None)

    def _seleccionar(self):
        """Selecciona una carpeta de proyecto"""
        if self._hilo and self._hilo.isRunning():
            return

        ruta = QFileDialog.getExistingDirectory(
            self, "Seleccionar",
            self.config.config.get('ultima_carpeta', '')
        )

        if ruta:
            self.abrir_carpeta(Path(ruta))

    def _opciones(self):
        """Muestra el diálogo de carpetas y filtros de escaneo"""
        if not self.ruta or (self._hilo and self._hilo.isRunning()):
            return

        dlg = DialogoSelectorCarpetas(self.ruta, self._opciones_filtro(), self)
        if dlg.exec():
            opciones = dlg.obtener_opciones()
            self.config.config['excluir_tests'] = opciones.excluir_tests
            self.config.config['excluir_minificados'] = opciones.excluir_minificados
            self.config.config['tamano_max_kb'] = opciones.tamano_max_kb
            self.config.guardar()

            self._escanear(carpetas=dlg.obtener_seleccionadas(), filtro=opciones)

    def _dependencias(self):
        """Analiza dependencias de un archivo"""
        if not self.ruta or (self._hilo and self._hilo.isRunning()):
            return

        dlg = DialogoAnalizarDep(self.ruta, self)
        if dlg.exec() and dlg.archivo:
            self._escanear(dep=dlg.archivo)

    def _escanear(self, carpetas=None, dep=None, filtro=None):
        """Inicia el escaneo en background thread"""
        if not self.ruta:
            return

        # Si hay un escaneo activo, cancelarlo
        if self._hilo and self._hilo.isRunning():
            self._cancelar_escaneo()
            return

        if filtro is None:
            filtro = self._opciones_filtro()

        # Sin carpetas elegidas vale None, no una lista vacía ni un bool
        carpetas = list(carpetas) if carpetas else None

        self._carpetas_pendientes = carpetas
        self._dep_pendiente = dep
        self._filtro_pendiente = filtro

        # Preparar UI para escaneo
        self._ui_escaneando(True)

        # Crear y conectar el thread
        self._hilo = HiloEscaneo(
            self.ruta, carpetas, dep,
            opciones_filtro=filtro, parent=self
        )
        self._hilo.progreso.connect(self._on_progreso)
        self._hilo.completado.connect(self._on_completado)
        self._hilo.error.connect(self._on_error)
        self._hilo.finished.connect(lambda: self._ui_escaneando(False))
        self._hilo.start()

    def _cancelar_escaneo(self):
        """Solicita la cancelación del escaneo en curso"""
        if self._hilo and self._hilo.isRunning():
            self._hilo.requestInterruption()
            self._hilo.wait(3000)   # esperar máximo 3 segundos
        self._ui_escaneando(False)
        self.lbl_progreso.setText("Escaneo cancelado")
        QTimer.singleShot(2000, lambda: self.lbl_progreso.setText(""))

    # ── SLOTS DEL THREAD ────────────────────────────────────────────────────

    def _on_progreso(self, archivo: str, numero: int):
        """Actualiza el label de progreso con el archivo actual"""
        nombre_corto = archivo if len(archivo) <= 40 else f"...{archivo[-37:]}"
        self.lbl_progreso.setText(f"Procesando archivo {numero}: {nombre_corto}")

    def _on_completado(self, resultado):
        """Recibe el resultado y actualiza la UI"""
        self.modelo.establecer_resultado(resultado)
        self._carpetas_usadas = self._carpetas_pendientes
        self._filtro_usado = self._filtro_pendiente
        self._actualizar()
        self.btn_cop.setEnabled(True)
        self.btn_exp.setEnabled(True)
        self.config.agregar_proyecto_reciente(str(self.ruta))

        # Mostrar info de dependencias si aplica
        if self._dep_pendiente:
            QMessageBox.information(
                self, "Completo",
                f"Encontrados {len(resultado.archivos)} archivos relacionados"
            )
            self._dep_pendiente = None

        # Un perfil cargado deja la selección para después del escaneo
        if self._seleccion_pendiente:
            self._aplicar_seleccion_guardada(self._seleccion_pendiente)
            self._seleccion_pendiente = None
            aviso = (
                f"✅ Perfil cargado: {len(resultado.archivos)} archivos, "
                f"{len(self.modelo.exclusiones())} fuera"
            )
        else:
            aviso = f"✅ {len(resultado.archivos)} archivos procesados"

        self.lbl_progreso.setText(aviso)
        QTimer.singleShot(3000, lambda: self.lbl_progreso.setText(""))

    def _on_error(self, mensaje: str):
        """Muestra error del thread"""
        QMessageBox.critical(self, "❌ Error al escanear", mensaje)

    # ── HELPERS DE UI ───────────────────────────────────────────────────────

    def _ui_escaneando(self, escaneando: bool):
        """Activa/desactiva controles según si hay escaneo en curso"""
        self.barra_progreso.setVisible(escaneando)
        self.lbl_progreso.setVisible(True)

        if escaneando:
            self.btn_esc.setText("⏹ Cancelar")
            self.btn_esc.setStyleSheet("color: #d32f2f;")
        else:
            self.btn_esc.setText("Escanear")
            self.btn_esc.setStyleSheet("")
            self.barra_progreso.setVisible(False)

        # Deshabilitar botones que no deben usarse durante el escaneo
        for btn in [self.btn_sel, self.btn_opc, self.btn_dep, self.btn_nvo]:
            btn.setEnabled(not escaneando)

        # Las acciones de selección recién valen si hay un escaneo hecho
        hay_resultado = bool(self.modelo.resultado)
        for btn in self._botones_seleccion:
            btn.setEnabled(not escaneando and hay_resultado)

        # Restaurar el perfil no pide un escaneo previo, alcanza con la carpeta
        self.btn_cargar_perfil.setEnabled(not escaneando and bool(self.ruta))

    def _actualizar(self):
        """Reconstruye el árbol y refresca métricas y vista previa"""
        self._poblar_arbol()
        self._refrescar_metricas()

    def _refrescar_metricas(self):
        """Actualiza métricas, recomendación y vista previa con la selección actual"""
        m = self.modelo.metricas()

        if m['archivos_excluidos']:
            self.lbl_files.setText(
                f"Archivos: {m['total_archivos']} / {m['archivos_totales']}"
            )
            self.lbl_files.setToolTip(
                f"{m['archivos_excluidos']} archivo(s) fuera de la selección"
            )
        else:
            self.lbl_files.setText(f"Archivos: {m['archivos_totales']}")
            self.lbl_files.setToolTip("")

        self.lbl_ign.setText(f"Ignorados: {m['archivos_ignorados']}")
        self.lbl_lines.setText(f"Líneas: {m['total_lineas']:,}")
        self.lbl_tokens.setText(f"Tokens: {m['tokens']:,}")

        motor = m['tokenizador']
        if m['tokens_exactos']:
            self.lbl_tokens.setToolTip(f"Conteo exacto — {motor}")
        else:
            self.lbl_tokens.setToolTip(
                f"Estimación aproximada — {motor}\n"
                "Instalá tiktoken para un conteo exacto."
            )

        self._tokens_actuales = m['tokens']
        self._actualizar_recomendacion()
        self._recalcular_totales_arbol()
        self.txt_prev.setPlainText(self.modelo.generar_contexto())

    def _actualizar_recomendacion(self):
        """Ajusta el aviso según el modelo objetivo elegido"""
        if not self.modelo.resultado:
            self.lbl_rec.setText("")
            return

        t = self._tokens_actuales
        limite = self.cmb_modelo.currentData()

        if limite is None:
            # Guía general cuando no hay un modelo objetivo fijo
            if t > 180000:
                texto = "⚠️ MUY GRANDE\nUsá Opciones o Analizar"
                color, negrita = "#d32f2f", "bold"
            elif t > 128000:
                texto = "⚠️ Grande para GPT-4\n✅ Claude lo acepta"
                color, negrita = "#f57c00", "normal"
            elif t > 100000:
                texto = "✅ Claude sin problema\n⚠️ GPT-4 al límite"
                color, negrita = "#388e3c", "normal"
            else:
                texto = "✅ Entra en GPT-4 y Claude"
                color, negrita = "#388e3c", "normal"
        else:
            etiqueta = self.cmb_modelo.currentText()
            pct = t / limite * 100
            if t <= limite:
                texto = (
                    f"✅ Entra en {etiqueta}\n"
                    f"Uso: {pct:.1f}% ({t:,}/{limite:,})"
                )
                color, negrita = "#388e3c", "normal"
            else:
                texto = (
                    f"⚠️ Excede {etiqueta}\n"
                    f"Sobran {t - limite:,} tokens"
                )
                color, negrita = "#d32f2f", "bold"

        self.lbl_rec.setText(texto)
        self.lbl_rec.setStyleSheet(f"color: {color}; font-weight: {negrita};")

    # ── ÁRBOL Y SELECCIÓN ───────────────────────────────────────────────────

    def _poblar_arbol(self):
        """Puebla el árbol con tamaño, tokens y checkboxes"""
        self.tree.clear()
        resultado = self.modelo.resultado
        if not resultado:
            self._mapa_archivos = {}
            return

        self._mapa_archivos = {
            clave_ruta(info.ruta_relativa): info for info in resultado.archivos
        }

        arbol = resultado.arbol_directorios or {}

        # El escáner guarda los archivos de la raíz bajo la clave '.' y las
        # carpetas de primer nivel como claves hermanas. Se fusionan para que
        # el árbol muestre raíz y subcarpetas juntas.
        raiz = dict(arbol.get('.', {}))
        for nombre, sub in arbol.items():
            if nombre != '.':
                raiz[nombre] = sub

        self._poblando = True
        self._agregar_items(self.tree, raiz, '')
        self._poblando = False

        self._sincronizar_seleccion_arbol()
        self.tree.expandToDepth(0)

    def _agregar_items(self, padre, dic: Dict, prefijo: str = ''):
        """Crea los items del árbol con su checkbox y sus valores"""
        for nombre, sub in sorted(dic.items(), key=lambda x: (x[1] is not None, x[0])):
            rel = f"{prefijo}/{nombre}" if prefijo else nombre
            item = QTreeWidgetItem(padre)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

            if sub is not None:
                item.setText(0, f"📁 {nombre}")
                item.setCheckState(0, Qt.Checked)
                self._agregar_items(item, sub, rel)
            else:
                clave = clave_ruta(rel)
                item.setText(0, nombre)
                item.setData(0, Qt.UserRole, clave)
                info = self._mapa_archivos.get(clave)
                if info:
                    item.setText(1, self._formato_kb(info.tamano_bytes))
                    item.setText(2, f"{info.token_count:,}" if info.token_count else "—")
                    item.setToolTip(2, f"{info.token_count:,} tokens")
                excluido = self.modelo.esta_excluido(clave)
                item.setCheckState(0, Qt.Unchecked if excluido else Qt.Checked)

    def _on_item_cambiado(self, item: QTreeWidgetItem, columna: int):
        """Reacciona a los checkboxes del árbol"""
        if self._poblando or columna != 0:
            return

        estado = item.checkState(0)
        if estado == Qt.PartiallyChecked:
            return

        claves = self._claves_de_item(item)
        if estado == Qt.Checked:
            self.modelo.incluir(claves)
        else:
            self.modelo.excluir(claves)

        if item.childCount():
            self._marcar_subarbol(item, estado)
        self._actualizar_ancestros(item)
        self._timer_refresco.start()

    def _claves_de_item(self, item: QTreeWidgetItem) -> List[str]:
        """Claves de archivo del item, o de todo su subárbol si es carpeta"""
        if item.childCount() == 0:
            clave = item.data(0, Qt.UserRole)
            return [clave] if clave else []
        claves = []
        for i in range(item.childCount()):
            claves.extend(self._claves_de_item(item.child(i)))
        return claves

    def _marcar_subarbol(self, item: QTreeWidgetItem, estado):
        """Marca todo el subárbol con el mismo estado (sin disparar señales)"""
        self._poblando = True
        self._marcar_recursivo(item, estado)
        self._poblando = False

    def _marcar_recursivo(self, item: QTreeWidgetItem, estado):
        item.setCheckState(0, estado)
        for i in range(item.childCount()):
            self._marcar_recursivo(item.child(i), estado)

    def _actualizar_ancestros(self, item: QTreeWidgetItem):
        """Recalcula el estado tri-state de las carpetas superiores"""
        padre = item.parent()
        while padre is not None:
            estados = {
                padre.child(i).checkState(0) for i in range(padre.childCount())
            }
            if estados == {Qt.Checked}:
                nuevo = Qt.Checked
            elif estados == {Qt.Unchecked}:
                nuevo = Qt.Unchecked
            else:
                nuevo = Qt.PartiallyChecked

            if padre.checkState(0) != nuevo:
                self._poblando = True
                padre.setCheckState(0, nuevo)
                self._poblando = False

            padre = padre.parent()

    def _sincronizar_seleccion_arbol(self):
        """Sincroniza los checkboxes del árbol con la selección del modelo"""
        self._poblando = True
        raiz = self.tree.invisibleRootItem()
        for i in range(raiz.childCount()):
            self._sincronizar_item(raiz.child(i))
        self._poblando = False

    def _sincronizar_item(self, item: QTreeWidgetItem):
        """Ajusta el estado del item (y su rama) y devuelve su estado final"""
        if item.childCount() == 0:
            clave = item.data(0, Qt.UserRole)
            estado = Qt.Unchecked if self.modelo.esta_excluido(clave) else Qt.Checked
            item.setCheckState(0, estado)
            return estado

        estados = [
            self._sincronizar_item(item.child(i)) for i in range(item.childCount())
        ]
        if all(e == Qt.Checked for e in estados):
            estado = Qt.Checked
        elif all(e == Qt.Unchecked for e in estados):
            estado = Qt.Unchecked
        else:
            estado = Qt.PartiallyChecked
        item.setCheckState(0, estado)
        return estado

    def _recalcular_totales_arbol(self):
        """Recalcula los totales por carpeta según lo que está seleccionado"""
        raiz = self.tree.invisibleRootItem()
        for i in range(raiz.childCount()):
            self._recalcular_item(raiz.child(i))

    def _recalcular_item(self, item: QTreeWidgetItem) -> tuple:
        """Devuelve (tokens, bytes) seleccionados de la rama y refresca el item"""
        if item.childCount() == 0:
            info = self._mapa_archivos.get(item.data(0, Qt.UserRole))
            if not info:
                return 0, 0

            incluido = item.checkState(0) == Qt.Checked
            self._pintar(item, incluido)
            if incluido:
                item.setToolTip(2, f"{info.token_count:,} tokens")
                return info.token_count, info.tamano_bytes

            item.setToolTip(2, f"{info.token_count:,} tokens — excluido")
            return 0, 0

        tokens = 0
        bytes_ = 0
        for i in range(item.childCount()):
            t, b = self._recalcular_item(item.child(i))
            tokens += t
            bytes_ += b

        item.setText(1, self._formato_kb(bytes_))
        item.setText(2, f"{tokens:,}" if tokens else "")
        item.setToolTip(2, f"{tokens:,} tokens seleccionados en esta carpeta")
        return tokens, bytes_

    @staticmethod
    def _pintar(item: QTreeWidgetItem, incluido: bool):
        """Tacha el nombre de los archivos que quedaron fuera de la selección"""
        fuente = item.font(0)
        if fuente.strikeOut() != (not incluido):
            fuente.setStrikeOut(not incluido)
            item.setFont(0, fuente)

    def _seleccionar_todo(self):
        """Incluye todos los archivos en el contexto"""
        self.modelo.incluir_todo()
        self._sincronizar_seleccion_arbol()
        self._refrescar_metricas()

    def _deseleccionar_todo(self):
        """Excluye todos los archivos del contexto"""
        self.modelo.excluir_todo()
        self._sincronizar_seleccion_arbol()
        self._refrescar_metricas()

    def _recortar(self):
        """Quita archivos hasta bajar del objetivo de tokens indicado"""
        if not self.modelo.resultado:
            return

        limite = self.cmb_modelo.currentData()
        actual = self._tokens_actuales
        sugerido = limite if limite else max(1000, int(actual * 0.9))

        objetivo, ok = QInputDialog.getInt(
            self, "Recortar selección", "Objetivo de tokens:",
            sugerido, 100, 10_000_000, 1000
        )
        if not ok:
            return

        quitados, ahorrados = self.modelo.recortar_a(objetivo)
        self._sincronizar_seleccion_arbol()
        self._refrescar_metricas()

        if quitados:
            QMessageBox.information(
                self, "Recortar",
                f"Se quitaron {quitados} archivo(s).\n"
                f"Ahorro: {ahorrados:,} tokens.\n"
                f"Quedan {self._tokens_actuales:,} tokens."
            )
        else:
            QMessageBox.information(
                self, "Recortar",
                f"Ya estaba dentro del objetivo ({self._tokens_actuales:,} tokens)."
            )

    def _guardar_perfil(self):
        """Guarda cómo está configurado el proyecto en este momento"""
        if not self.ruta or not self.modelo.resultado:
            return

        filtros = self._opciones_filtro()
        optimizacion = {
            'quitar_comentarios': self.chk_comentarios.isChecked(),
            'quitar_lineas_vacias': self.chk_vacias.isChecked(),
        }
        perfil = {
            'carpetas': self._carpetas_usadas,
            'filtros': {
                'excluir_tests': filtros.excluir_tests,
                'excluir_minificados': filtros.excluir_minificados,
                'tamano_max_kb': filtros.tamano_max_kb,
            },
            'optimizacion': optimizacion,
            'modelo': self.cmb_modelo.currentText(),
            'plantilla': self.cmb_plantilla.currentText(),
            'seleccion': self.modelo.exclusiones(),
            'guardado': datetime.now().isoformat(timespec='seconds'),
        }
        self.config.guardar_perfil(str(self.ruta), perfil)

        QMessageBox.information(
            self, "Perfil",
            f"Perfil guardado para {self.ruta.name}:\n"
            f"• {len(perfil['seleccion'])} archivo(s) fuera de la selección\n"
            f"• Optimización: {self._resumen_optimizacion(optimizacion)}\n"
            f"• Plantilla: {perfil['plantilla']}"
        )

    def _cargar_perfil(self):
        """Restaura el perfil guardado del proyecto"""
        if not self.ruta:
            return

        perfil = self.config.obtener_perfil(str(self.ruta))
        if not perfil:
            QMessageBox.information(
                self, "Perfil",
                "No hay un perfil guardado para este proyecto."
            )
            return

        self._aplicar_perfil_a_controles(perfil)

        guardados = perfil.get('filtros') or {}
        filtros = OpcionesFiltro(
            excluir_tests=bool(guardados.get('excluir_tests', False)),
            excluir_minificados=bool(guardados.get('excluir_minificados', True)),
            tamano_max_kb=int(guardados.get('tamano_max_kb', 1024)),
        )
        carpetas = perfil.get('carpetas') or None   # perfiles viejos: `false`
        seleccion = perfil.get('seleccion') or []

        # Con otro escaneo del que pide el perfil hay que volver a escanear.
        # La selección se aplica cuando el hilo termine (ver _on_completado).
        if self._requiere_rescan(carpetas, filtros):
            self.config.config['excluir_tests'] = filtros.excluir_tests
            self.config.config['excluir_minificados'] = filtros.excluir_minificados
            self.config.config['tamano_max_kb'] = filtros.tamano_max_kb
            self.config.guardar()

            self._seleccion_pendiente = seleccion
            self._escanear(carpetas=carpetas, filtro=filtros)
            return

        self._aplicar_seleccion_guardada(seleccion)
        QMessageBox.information(
            self, "Perfil",
            "Perfil aplicado sobre el escaneo actual "
            f"({len(self.modelo.exclusiones())} archivo(s) fuera)."
        )

    def _aplicar_perfil_a_controles(self, perfil: Dict):
        """Deja los controles como los dejó el perfil, sin refrescos intermedios"""
        self._cargando_perfil = True
        try:
            opt = perfil.get('optimizacion') or {}
            self.chk_comentarios.setChecked(bool(opt.get('quitar_comentarios', False)))
            self.chk_vacias.setChecked(bool(opt.get('quitar_lineas_vacias', False)))

            plantilla = perfil.get('plantilla')
            if plantilla and self.cmb_plantilla.findText(plantilla) >= 0:
                self.cmb_plantilla.setCurrentText(plantilla)

            modelo = perfil.get('modelo')
            idx = self.cmb_modelo.findText(modelo) if modelo else -1
            if idx >= 0:
                self.cmb_modelo.setCurrentIndex(idx)
        finally:
            self._cargando_perfil = False

        # Se aplican y persisten una sola vez, con un solo refresco al final
        self._on_optimizacion_cambiada()
        self._on_plantilla_cambiada()

    def _requiere_rescan(self, carpetas, filtros: OpcionesFiltro) -> bool:
        """True si el escaneo actual no cubre lo que pide el perfil"""
        if not self.modelo.resultado:
            return True
        if sorted(carpetas or []) != sorted(self._carpetas_usadas or []):
            return True
        return filtros != self._filtro_usado

    def _aplicar_seleccion_guardada(self, excluidos):
        """Aplica una lista de rutas excluidas al escaneo actual"""
        vigentes = set(self.modelo.claves())
        self.modelo.incluir_todo()
        self.modelo.excluir([c for c in excluidos if c in vigentes])
        self._sincronizar_seleccion_arbol()
        self._refrescar_metricas()

    @staticmethod
    def _resumen_optimizacion(opt: Dict) -> str:
        """Describe las optimizaciones activas para el mensaje de confirmación"""
        activas = [
            nombre for clave, nombre in (
                ('quitar_comentarios', 'sin comentarios'),
                ('quitar_lineas_vacias', 'sin líneas vacías'),
            ) if opt.get(clave)
        ]
        return ', '.join(activas) if activas else 'ninguna'

    @staticmethod
    def _formato_kb(bytes_: int) -> str:
        """Formatea un tamaño en bytes como B/KB/MB legibles"""
        if not bytes_:
            return ""
        if bytes_ < 1024:
            return f"{bytes_} B"
        kb = bytes_ / 1024
        if kb >= 1024:
            return f"{kb / 1024:,.1f} MB"
        return f"{kb:,.1f} KB"

    # ── PORTAPAPELES Y EXPORTACIÓN ──────────────────────────────────────────

    def _copiar(self):
        """Copia el contexto al portapapeles"""
        QApplication.clipboard().setText(self.modelo.generar_contexto_markdown())
        self.btn_cop.setText("✅ Copiado!")
        self.btn_cop.setEnabled(False)

        QTimer.singleShot(2000, lambda: (
            self.btn_cop.setText("📋 Copiar"),
            self.btn_cop.setEnabled(True)
        ))

    def _buscar(self, adelante=True):
        """Busca texto en la vista previa"""
        txt = self.txt_busq.text()
        if not txt:
            return

        if adelante:
            if not self.txt_prev.find(txt):
                self.txt_prev.moveCursor(QTextCursor.Start)
                self.txt_prev.find(txt)
        else:
            from PySide6.QtGui import QTextDocument
            if not self.txt_prev.find(txt, QTextDocument.FindBackward):
                self.txt_prev.moveCursor(QTextCursor.End)
                self.txt_prev.find(txt, QTextDocument.FindBackward)

    def _exportar(self):
        """Exporta el contexto a archivo"""
        if self.config.config.get('mostrar_advertencia_seguridad', True):
            from PySide6.QtWidgets import QCheckBox

            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("⚠️ Advertencia")
            msg.setText("Verificar contenido antes de exportar")
            msg.setInformativeText(
                "Asegúrate de no incluir:\n"
                "• API keys\n"
                "• Contraseñas\n"
                "• Info confidencial"
            )

            cb = QCheckBox("He verificado")
            msg.setCheckBox(cb)
            msg.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)

            if msg.exec() != QMessageBox.Ok or not cb.isChecked():
                return

        nombre = f"contexto_{self.ruta.name}.md"
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar",
            str(Path.home() / nombre),
            "Markdown (*.md);;Texto plano (*.txt)"
        )

        if ruta:
            try:
                if ruta.lower().endswith('.txt'):
                    contenido = self.modelo.generar_contexto()
                else:
                    contenido = self.modelo.generar_contexto_markdown()

                Path(ruta).write_text(contenido, encoding='utf-8')
                QMessageBox.information(self, "✅ Éxito", f"Guardado en:\n{ruta}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", str(e))
