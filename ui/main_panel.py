"""
Panel principal de la aplicación
"""
from pathlib import Path
from typing import Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QLabel, QSplitter, QMessageBox, QLineEdit, QApplication,
    QProgressBar, QComboBox, QHeaderView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor

from core import ConfigManager, HiloEscaneo
from .model_view import ModeloVista
from .dialogs import DialogoSelectorCarpetas, DialogoAnalizarDep


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
        self._tokens_actuales = 0
        self._mapa_archivos = {}
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
        self.btn_esc.clicked.connect(self._escanear)
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

    def _crear_area_arbol(self, layout):
        """Crea el área con árbol y métricas"""
        split = QSplitter(Qt.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Archivos", "Tamaño", "Tokens"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        split.addWidget(self.tree)

        metricas = QWidget()
        ml = QVBoxLayout(metricas)

        ml.addWidget(QLabel("Modelo objetivo:"))
        self.cmb_modelo = QComboBox()
        for etiqueta, limite in MODELOS_OBJETIVO:
            self.cmb_modelo.addItem(etiqueta, limite)
        self._restaurar_modelo()
        self.cmb_modelo.currentIndexChanged.connect(self._on_modelo_cambiado)
        ml.addWidget(self.cmb_modelo)

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

    # ── ACCIONES ────────────────────────────────────────────────────────────

    def _nuevo(self):
        """Reinicia para escanear otro proyecto"""
        if self._hilo and self._hilo.isRunning():
            return

        respuesta = QMessageBox.question(self, "Cambiar", "¿Cambiar a otro proyecto?")
        if respuesta != QMessageBox.Yes:
            return

        self.ruta = None
        self._tokens_actuales = 0
        self._mapa_archivos = {}
        self.lbl_ruta.setText("Sin proyecto")
        self.tree.clear()
        self.txt_prev.clear()
        self.txt_busq.clear()

        for lbl in [self.lbl_files, self.lbl_ign, self.lbl_lines, self.lbl_tokens]:
            lbl.setText(lbl.text().split(':')[0] + ": 0")
        self.lbl_tokens.setToolTip("")
        self.lbl_rec.setText("")

        for btn in [self.btn_esc, self.btn_opc, self.btn_dep,
                    self.btn_cop, self.btn_exp, self.btn_nvo]:
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
            self.ruta = Path(ruta)
            self.lbl_ruta.setText(str(self.ruta))

            for btn in [self.btn_esc, self.btn_opc, self.btn_dep, self.btn_nvo]:
                btn.setEnabled(True)

            self.config.config['ultima_carpeta'] = str(ruta)
            self.config.guardar()

    def _opciones(self):
        """Muestra diálogo de opciones de carpetas"""
        if not self.ruta or (self._hilo and self._hilo.isRunning()):
            return

        dlg = DialogoSelectorCarpetas(self.ruta, self)
        if dlg.exec():
            self._escanear(carpetas=dlg.obtener_seleccionadas())

    def _dependencias(self):
        """Analiza dependencias de un archivo"""
        if not self.ruta or (self._hilo and self._hilo.isRunning()):
            return

        dlg = DialogoAnalizarDep(self.ruta, self)
        if dlg.exec() and dlg.archivo:
            self._escanear(dep=dlg.archivo)

    def _escanear(self, carpetas=None, dep=None):
        """Inicia el escaneo en background thread"""
        if not self.ruta:
            return

        # Si hay un escaneo activo, cancelarlo
        if self._hilo and self._hilo.isRunning():
            self._cancelar_escaneo()
            return

        self._carpetas_pendientes = carpetas
        self._dep_pendiente = dep

        # Preparar UI para escaneo
        self._ui_escaneando(True)

        # Crear y conectar el thread
        self._hilo = HiloEscaneo(self.ruta, carpetas, dep, parent=self)
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

        self.lbl_progreso.setText(
            f"✅ {len(resultado.archivos)} archivos procesados"
        )
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

    def _actualizar(self):
        """Actualiza la interfaz con los resultados"""
        m = self.modelo.metricas()

        self.lbl_files.setText(f"Archivos: {m['total_archivos']}")
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
        self._poblar_arbol()
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

    def _poblar_arbol(self):
        """Puebla el árbol de archivos con tamaño y tokens"""
        self.tree.clear()
        resultado = self.modelo.resultado
        if not resultado:
            self._mapa_archivos = {}
            return

        self._mapa_archivos = {
            self._clave(info.ruta_relativa): info for info in resultado.archivos
        }

        arbol = resultado.arbol_directorios or {}

        # El escáner guarda los archivos de la raíz bajo la clave '.' y las
        # carpetas de primer nivel como claves hermanas. Se fusionan para que
        # el árbol muestre raíz y subcarpetas juntas.
        raiz = dict(arbol.get('.', {}))
        for nombre, sub in arbol.items():
            if nombre != '.':
                raiz[nombre] = sub

        self._agregar_items(self.tree, raiz, '')

    def _agregar_items(self, padre, dic: Dict, prefijo: str = '') -> tuple:
        """
        Agrega items al árbol recursivamente.
        Devuelve (tokens, bytes) acumulados de toda la rama.
        """
        tokens_total = 0
        bytes_total = 0

        for nombre, sub in sorted(dic.items(), key=lambda x: (x[1] is not None, x[0])):
            rel = f"{prefijo}/{nombre}" if prefijo else nombre
            item = QTreeWidgetItem(padre)

            if sub is not None:
                item.setText(0, f"📁 {nombre}")
                tokens, bytes_ = self._agregar_items(item, sub, rel)
                tokens_total += tokens
                bytes_total += bytes_
                item.setText(1, self._formato_kb(bytes_total))
                item.setText(2, f"{tokens:,}" if tokens else "")
                item.setToolTip(2, f"{tokens:,} tokens en esta carpeta")
            else:
                item.setText(0, nombre)
                info = self._mapa_archivos.get(self._clave(rel))
                if info:
                    tokens_total += info.token_count
                    bytes_total += info.tamano_bytes
                    item.setText(1, self._formato_kb(info.tamano_bytes))
                    item.setText(2, f"{info.token_count:,}" if info.token_count else "—")
                    item.setToolTip(2, f"{info.token_count:,} tokens")

        return tokens_total, bytes_total

    @staticmethod
    def _clave(ruta: str) -> str:
        """Normaliza separadores para comparar rutas relativas"""
        return ruta.replace('\\', '/')

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
