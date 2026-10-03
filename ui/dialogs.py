"""
Diálogos de la aplicación
"""
import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt

from core import FiltroArchivos

logger = logging.getLogger(__name__)


class DialogoSelectorCarpetas(QDialog):
    """Diálogo para seleccionar carpetas específicas a escanear"""
    
    def __init__(self, ruta: Path, parent=None):
        super().__init__(parent)
        self.ruta = ruta
        self.checks = {}
        self.setWindowTitle("Seleccionar Carpetas")
        self.setMinimumWidth(500)
        
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa la interfaz"""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selecciona carpetas a incluir:"))
        
        # Listar carpetas del proyecto
        filtro = FiltroArchivos()
        carpetas = sorted([
            x for x in self.ruta.iterdir()
            if x.is_dir() and not filtro.debe_ignorar_carpeta(x.name)
        ])
        
        for carpeta in carpetas:
            cb = QCheckBox(f"📁 {carpeta.name}/")
            cb.setChecked(True)
            layout.addWidget(cb)
            self.checks[carpeta.name] = cb
        
        # Botones
        btns = QHBoxLayout()
        
        btn_todo = QPushButton("Seleccionar Todo")
        btn_todo.clicked.connect(self._seleccionar_todo)
        
        btn_ninguno = QPushButton("Deseleccionar Todo")
        btn_ninguno.clicked.connect(self._deseleccionar_todo)
        
        btn_ok = QPushButton("Escanear")
        btn_ok.clicked.connect(self.accept)
        btn_ok.setDefault(True)
        
        btns.addWidget(btn_todo)
        btns.addWidget(btn_ninguno)
        btns.addStretch()
        btns.addWidget(btn_ok)
        
        layout.addLayout(btns)
    
    def _seleccionar_todo(self):
        """Selecciona todas las carpetas"""
        for cb in self.checks.values():
            cb.setChecked(True)
    
    def _deseleccionar_todo(self):
        """Deselecciona todas las carpetas"""
        for cb in self.checks.values():
            cb.setChecked(False)
    
    def obtener_seleccionadas(self) -> List[str]:
        """Retorna las carpetas seleccionadas"""
        return [nombre for nombre, cb in self.checks.items() if cb.isChecked()]


class DialogoAnalizarDep(QDialog):
    """Diálogo para análisis de dependencias"""
    
    def __init__(self, ruta: Path, parent=None):
        super().__init__(parent)
        self.ruta = ruta
        self.archivo = None
        self.setWindowTitle("Análisis de Dependencias")
        self.setMinimumSize(600, 400)
        
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa la interfaz"""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("🔍 Selecciona archivo para analizar sus dependencias:"))
        
        # Árbol de archivos
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Archivos")
        self.tree.itemDoubleClicked.connect(lambda *_: self._analizar())
        layout.addWidget(self.tree)
        
        self._poblar_arbol()
        
        # Botones
        btns = QHBoxLayout()
        btn_ok = QPushButton("Analizar")
        btn_ok.clicked.connect(self._analizar)
        btn_ok.setDefault(True)
        
        btns.addStretch()
        btns.addWidget(btn_ok)
        layout.addLayout(btns)
    
    def _poblar_arbol(self):
        """Puebla el árbol con archivos del proyecto"""
        filtro = FiltroArchivos()
        
        def agregar_items(parent, directorio):
            try:
                items = sorted(
                    directorio.iterdir(),
                    key=lambda x: (not x.is_dir(), x.name)
                )
            except Exception:
                logger.debug('Error iterando %s', directorio, exc_info=True)
                return
            
            for item in items:
                if item.is_dir():
                    if not filtro.debe_ignorar_carpeta(item.name):
                        tree_item = QTreeWidgetItem(parent, [f"📁 {item.name}"])
                        tree_item.setData(0, Qt.UserRole, str(item))
                        agregar_items(tree_item, item)
                elif filtro.debe_incluir_archivo(item):
                    tree_item = QTreeWidgetItem(parent, [item.name])
                    tree_item.setData(0, Qt.UserRole, str(item))
        
        agregar_items(self.tree, self.ruta)
        self.tree.expandAll()
    
    def _analizar(self):
        """Analiza el archivo seleccionado"""
        item = self.tree.currentItem()
        if not item:
            return
        
        ruta = Path(item.data(0, Qt.UserRole))
        if ruta.is_file():
            self.archivo = ruta
            self.accept()