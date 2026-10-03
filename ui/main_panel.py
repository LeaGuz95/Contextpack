"""
Panel principal de la aplicación
"""
from pathlib import Path
from typing import Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QLabel, QSplitter, QMessageBox, QLineEdit, QApplication,
    QProgressBar
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor

from core import ConfigManager, HiloEscaneo
from .model_view import ModeloVista
from .dialogs import DialogoSelectorCarpetas, DialogoAnalizarDep


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
        self.tree.setHeaderLabel("Archivos")
        split.addWidget(self.tree)

        metricas = QWidget()
        ml = QVBoxLayout(metricas)

        self.lbl_files  = QLabel("Archivos: 0")
        self.lbl_ign    = QLabel("Ignorados: 0")
        self.lbl_lines  = QLabel("Líneas: 0")
        self.lbl_tokens = QLabel("Tokens: ~0")
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

    # ── ACCIONES ────────────────────────────────────────────────────────────

    def _nuevo(self):
        """Reinicia para escanear otro proyecto"""
        if self._hilo and self._hilo.isRunning():
            return

        respuesta = QMessageBox.question(self, "Cambiar", "¿Cambiar a otro proyecto?")
        if respuesta != QMessageBox.Yes:
            return

        self.ruta = None
        self.lbl_ruta.setText("Sin proyecto")
        self.tree.clear()
        self.txt_prev.clear()
        self.txt_busq.clear()

        for lbl in [self.lbl_files, self.lbl_ign, self.lbl_lines, self.lbl_tokens]:
            lbl.setText(lbl.text().split(':')[0] + ": 0")
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
        self.lbl_tokens.setText(f"Tokens: ~{m['tokens']:,}")

        t = m['tokens']
        if t > 180000:
            self.lbl_rec.setText("⚠️ MUY GRANDE\nUsa Opciones o Analizar")
            self.lbl_rec.setStyleSheet("color: #d32f2f; font-weight: bold;")
        elif t > 128000:
            self.lbl_rec.setText("⚠️ Grande para GPT-4\n✅ Usar Claude")
            self.lbl_rec.setStyleSheet("color: #f57c00;")
        elif t > 100000:
            self.lbl_rec.setText("✅ Compatible Claude\n⚠️ GPT-4 al límite")
            self.lbl_rec.setStyleSheet("color: #388e3c;")
        else:
            self.lbl_rec.setText("✅ Compatible GPT-4 y Claude")
            self.lbl_rec.setStyleSheet("color: #388e3c;")

        self._poblar_arbol()
        self.txt_prev.setPlainText(self.modelo.generar_contexto())

    def _poblar_arbol(self):
        """Puebla el árbol de archivos"""
        self.tree.clear()
        arbol = self.modelo.resultado.arbol_directorios

        if '.' in arbol:
            self._agregar_items(self.tree, arbol['.'])
        else:
            self._agregar_items(self.tree, arbol)

    def _agregar_items(self, padre, dic: Dict):
        """Agrega items al árbol recursivamente"""
        for nombre, sub in sorted(dic.items(), key=lambda x: (x[1] is not None, x[0])):
            item = QTreeWidgetItem(padre)
            item.setText(0, f"📁 {nombre}" if sub is not None else nombre)
            if sub:
                self._agregar_items(item, sub)

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
