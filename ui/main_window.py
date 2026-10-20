"""
Ventana principal de la aplicación
"""
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel,
    QFrame, QHBoxLayout, QMessageBox, QMenu
)
from PySide6.QtGui import QIcon, QAction

from core import ConfigManager
from .model_view import ModeloVista
from .main_panel import VistaPanel

logger = logging.getLogger(__name__)


class VentanaPrincipal(QMainWindow):
    """Ventana principal de ContextPack"""

    def __init__(self, config: ConfigManager):
        super().__init__()
        self.config = config
        self.modelo = ModeloVista(config)

        self.setWindowTitle("ContextPack v1.10.1 — Pucha Soft")
        self.setGeometry(
            100, 100,
            config.config.get('ventana_ancho', 1200),
            config.config.get('ventana_alto', 850)
        )

        self._cargar_icono()
        self._crear_interfaz()
        self._crear_menu()

    def _cargar_icono(self):
        """Carga el icono de la aplicación"""
        try:
            for nombre in ['logo.ico', 'logo.png']:
                icono = Path(__file__).parent.parent / nombre
                if icono.exists():
                    self.setWindowIcon(QIcon(str(icono)))
                    break
        except Exception:
            logger.debug('No se pudo cargar el icono', exc_info=True)

    def _crear_interfaz(self):
        """Crea la interfaz central"""
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.panel = VistaPanel(self.modelo, self.config)
        layout.addWidget(self.panel)

        footer = self._crear_footer()
        layout.addWidget(footer)

        self.setCentralWidget(central)
        self.setAcceptDrops(True)

    @staticmethod
    def _carpeta_arrastrada(event):
        """Devuelve la primera carpeta local del arrastre, o None"""
        datos = event.mimeData()
        if not datos.hasUrls():
            return None
        for url in datos.urls():
            if url.isLocalFile():
                ruta = Path(url.toLocalFile())
                if ruta.is_dir():
                    return ruta
        return None

    def dragEnterEvent(self, event):
        """Acepta el arrastre solo si trae una carpeta local"""
        if self._carpeta_arrastrada(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Abre como proyecto la carpeta soltada sobre la ventana"""
        carpeta = self._carpeta_arrastrada(event)
        if carpeta is not None:
            self.panel.abrir_carpeta(carpeta)
            event.acceptProposedAction()

    def _crear_footer(self) -> QFrame:
        """Crea el footer con información"""
        footer = QFrame()
        footer.setObjectName("footer")
        footer.setMaximumHeight(36)

        fl = QHBoxLayout(footer)
        fl.setContentsMargins(12, 0, 12, 0)

        lbl_autor = QLabel("Desarrollado por <b>Leandro Guzmán</b> | Pucha Soft")
        lbl_autor.setStyleSheet("color: #5A5A7A; font-size: 11px;")

        lbl_ver = QLabel("v1.10.1")
        lbl_ver.setStyleSheet("color: #4A9FFF; font-size: 11px; font-weight: 600;")

        fl.addWidget(lbl_autor)
        fl.addStretch()
        fl.addWidget(lbl_ver)

        return footer

    def _crear_menu(self):
        """Crea el menú principal"""
        menu = self.menuBar().addMenu("Archivo")

        self.menu_rec = QMenu("Recientes", self)
        self._actualizar_recientes()
        menu.addMenu(self.menu_rec)
        menu.addSeparator()

        limpiar = QAction("Limpiar Historial", self)
        limpiar.triggered.connect(self._limpiar_historial)
        menu.addAction(limpiar)

        menu.addSeparator()
        menu.addAction("Salir", self.close)

        ayuda = self.menuBar().addMenu("Ayuda")
        ayuda.addAction("Acerca de", self._mostrar_acerca_de)

    def _actualizar_recientes(self):
        """Actualiza el menú de proyectos recientes"""
        self.menu_rec.clear()

        recientes = self.config.config.get('proyectos_recientes', [])
        if not recientes:
            vacio = QAction("(vacío)", self)
            vacio.setEnabled(False)
            self.menu_rec.addAction(vacio)
            return

        for ruta in recientes:
            if Path(ruta).exists():
                accion = QAction(f"📁 {Path(ruta).name}", self)
                accion.triggered.connect(
                    lambda checked, r=ruta: self._abrir_reciente(r)
                )
                self.menu_rec.addAction(accion)

    def _limpiar_historial(self):
        """Limpia el historial de proyectos recientes"""
        self.config.establecer(proyectos_recientes=[])
        self._actualizar_recientes()

    def _abrir_reciente(self, ruta: str):
        """Abre un proyecto reciente"""
        self.panel.abrir_carpeta(Path(ruta))

    def _mostrar_acerca_de(self):
        """Muestra el diálogo Acerca de"""
        QMessageBox.about(
            self,
            "Acerca de",
            "<h2>ContextPack v1.10.1 </h2>"
            "<p><b>Desarrollado por:</b> Leandro Guzmán<br>"        
            "<p>Generador de contexto para IA</p>"
            "<hr><p><i>© 2026 Pucha Soft</i></p>"
        )

    def closeEvent(self, event):
        """Maneja el cierre de la ventana"""
        # Un escaneo a medio terminar deja el hilo vivo: hay que frenarlo
        # antes de aceptar el cierre o Qt avisa al destruir la ventana.
        self.panel.detener_escaneo()
        self.config.establecer(
            ventana_ancho=self.width(),
            ventana_alto=self.height(),
        )
        event.accept()
